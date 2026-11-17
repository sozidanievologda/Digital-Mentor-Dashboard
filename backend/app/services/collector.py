import logging
import threading
from collections import Counter
from datetime import date, datetime, timedelta

from ..utils import config
from . import storage
from .crm_service import fetch_all_managers, fetch_all_users

logger = logging.getLogger(__name__)

_refresh_lock = threading.Lock()
_schedule_lock = threading.Lock()
_scheduled = False
_stop_event = threading.Event()
_scheduler_thread = None


def _tag_matches(name: str) -> bool:
    if config.PROJECT_TAG_NAMES:
        return name in config.PROJECT_TAG_NAMES
    return name.startswith(config.PROJECT_TAG_PREFIX)


def project_user_ids(users):
    """Ids of users tagged as participants of the project."""
    ids = set()
    for user in users:
        user_id = user.get("id")
        if user_id is None:
            continue
        if any(
            isinstance(tag, dict) and _tag_matches(tag.get("name", ""))
            for tag in (user.get("tags") or [])
        ):
            ids.add(user_id)
    return ids


def _parse_day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _cumulative_counts(created_dates, start: date, end: date):
    """Daily cumulative counts of records created on or before each day."""
    days = [day for day in (_parse_day(value) for value in created_dates) if day]
    baseline = sum(1 for day in days if day < start)
    per_day = Counter(day.isoformat() for day in days if start <= day <= end)

    result = {}
    current = baseline
    cursor = start
    while cursor <= end:
        current += per_day.get(cursor.isoformat(), 0)
        result[cursor] = current
        cursor += timedelta(days=1)
    return result


def _backfill_snapshots():
    """Approximate history from record creation dates until live snapshots exist.

    The CRM does not expose when a project tag was assigned, so the backfill is
    based on user creation dates and is marked with source='backfill'.
    """
    try:
        start = date.fromisoformat(config.PROJECT_START_DATE)
    except ValueError:
        logger.warning("Некорректный PROJECT_START_DATE, бэкфилл пропущен")
        return

    end = date.today() - timedelta(days=1)
    if start > end:
        return

    project = _cumulative_counts(storage.get_project_created_dates(), start, end)
    total = _cumulative_counts(storage.get_all_user_created_dates(), start, end)
    volunteers = _cumulative_counts(storage.get_manager_created_dates(), start, end)

    taken_at = datetime.now().isoformat(timespec="seconds")
    rows = [
        (
            day.isoformat(),
            taken_at,
            project[day],
            total[day],
            volunteers[day],
        )
        for day in sorted(project)
    ]
    storage.insert_snapshots(rows, source="backfill")
    logger.info(f"История заполнена оценочными данными: {len(rows)} дней")


def refresh_data(blocking=True) -> bool:
    """Pull data from the CRM and persist a snapshot. Returns False if busy."""
    if not _refresh_lock.acquire(blocking=blocking):
        logger.info("Обновление уже выполняется, пропускаю повторный запрос")
        return False

    try:
        storage.set_meta("last_attempt_at", datetime.now().isoformat(timespec="seconds"))
        users = fetch_all_users()
        managers = fetch_all_managers()

        project_ids = project_user_ids(users)
        storage.replace_users(users, project_ids)
        storage.replace_managers(managers)

        if storage.min_snapshot_date() is None:
            _backfill_snapshots()

        today = date.today().isoformat()
        storage.upsert_snapshot(
            today,
            datetime.now().isoformat(timespec="seconds"),
            len(project_ids),
            len(users),
            len(managers),
            source="live",
        )
        storage.set_meta("last_success_at", datetime.now().isoformat(timespec="seconds"))
        storage.set_meta("last_error", "")
        logger.info(
            f"Данные обновлены: участников проекта {len(project_ids)}, "
            f"всего пользователей {len(users)}, волонтёров {len(managers)}"
        )
        return True
    except Exception as exc:
        storage.set_meta("last_error", str(exc))
        logger.error(f"Не удалось обновить данные из CRM: {exc}")
        raise
    finally:
        _refresh_lock.release()


def get_data_status() -> str:
    last_success = storage.get_meta("last_success_at")
    if not last_success:
        return "error"
    try:
        age = (datetime.now() - datetime.fromisoformat(last_success)).total_seconds()
    except ValueError:
        return "error"
    return "live" if age <= config.DATA_TTL_SECONDS else "stale"


def ensure_fresh():
    """Kick off a background refresh when the cached snapshot is stale."""
    if get_data_status() == "live":
        return

    global _scheduled
    with _schedule_lock:
        if _scheduled:
            return
        _scheduled = True

    def run():
        global _scheduled
        try:
            refresh_data(blocking=False)
        except Exception:
            pass
        finally:
            with _schedule_lock:
                _scheduled = False

    threading.Thread(target=run, name="crm-refresh-on-demand", daemon=True).start()


def startup_refresh():
    storage.init_db()
    if storage.get_latest_snapshot() is None:
        try:
            refresh_data(blocking=True)
        except Exception:
            logger.warning("Первичная загрузка из CRM не удалась, работаю без данных")
    ensure_fresh()


def _scheduler_loop():
    while not _stop_event.wait(config.REFRESH_INTERVAL_SECONDS):
        try:
            refresh_data(blocking=False)
        except Exception:
            pass


def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, name="crm-scheduler", daemon=True
    )
    _scheduler_thread.start()
    logger.info(f"Планировщик обновлений запущен (интервал {config.REFRESH_INTERVAL_SECONDS} с)")


def stop_scheduler():
    _stop_event.set()
