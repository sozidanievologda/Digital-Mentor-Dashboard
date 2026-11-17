import logging
from datetime import date, timedelta

from fastapi import HTTPException, status

from ..utils import config
from . import collector, storage

logger = logging.getLogger(__name__)

MAX_HISTORY_DAYS = 730
PERIOD_DAYS = {"7d": 7, "30d": 30, "90d": 90, "quarter": 90}


def _parse_day(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректная дата в параметре {field_name}: {value}",
        )


def get_current_metrics():
    snapshot = storage.get_latest_snapshot()
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Данные ещё не загружены из CRM",
        )

    data_status = collector.get_data_status()
    if data_status != "live":
        collector.ensure_fresh()

    last_success_at = storage.get_meta("last_success_at")
    last_error = storage.get_meta("last_error") or None

    return {
        "pensioners_count": snapshot["project_users"],
        "volunteers_count": snapshot["volunteers"],
        "total_users": snapshot["total_users"],
        "last_updated": snapshot["taken_at"],
        "last_success_at": last_success_at,
        "status": "active" if data_status == "live" else "stale",
        "data_status": data_status,
        "error": last_error,
    }


def refresh_and_get_metrics():
    try:
        collector.refresh_data(blocking=True)
    except Exception as exc:
        logger.warning(f"Ручное обновление не удалось: {exc}")
    return get_current_metrics()


def _resolve_range(period: str, start: str, end: str):
    if start or end:
        if not (start and end):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для произвольного интервала нужны оба параметра: start и end",
            )
        start_date = _parse_day(start, "start")
        end_date = _parse_day(end, "end")
        period = "custom"
    else:
        end_date = date.today()
        if period == "all":
            first = storage.min_snapshot_date()
            start_date = date.fromisoformat(first) if first else date.fromisoformat(
                config.PROJECT_START_DATE
            )
        else:
            days = PERIOD_DAYS.get(period)
            if days is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="period должен быть одним из: 7d, 30d, 90d, quarter, all",
                )
            start_date = end_date - timedelta(days=days - 1)

    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата начала не может быть позже даты окончания",
        )
    if (end_date - start_date).days > MAX_HISTORY_DAYS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Максимальный интервал — {MAX_HISTORY_DAYS} дней",
        )
    return period, start_date, end_date


def _build_series(start_date: date, end_date: date):
    rows = storage.get_snapshots(start_date.isoformat(), end_date.isoformat())
    by_day = {row["snapshot_date"]: row for row in rows}
    approximate = any(row["source"] == "backfill" for row in rows)

    baseline = storage.get_snapshot_before(start_date.isoformat())
    pensioners = baseline["project_users"] if baseline else None
    volunteers = baseline["volunteers"] if baseline else None

    pensioners_series = []
    volunteers_series = []
    cursor = start_date
    while cursor <= end_date:
        row = by_day.get(cursor.isoformat())
        if row:
            pensioners = row["project_users"]
            volunteers = row["volunteers"]
        pensioners_series.append({"date": cursor.isoformat(), "count": pensioners})
        volunteers_series.append({"date": cursor.isoformat(), "count": volunteers})
        cursor += timedelta(days=1)

    return pensioners_series, volunteers_series, approximate


def get_history_data(period: str = "30d", start: str = None, end: str = None):
    collector.ensure_fresh()

    try:
        period, start_date, end_date = _resolve_range(period, start, end)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Ошибка разбора периода: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректные параметры периода",
        )

    pensioners, volunteers, approximate = _build_series(start_date, end_date)

    return {
        "period": period,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "source": "snapshots",
        "approximate": approximate,
        "pensioners": pensioners,
        "volunteers": volunteers,
    }
