import logging
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from dateutil.parser import parse as parse_date

from .crm_service import fetch_all_users, fetch_all_managers

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # seconds (5 minutes)

# One cached snapshot of the CRM data is shared by metrics and history, so a
# dashboard load fetches the CRM once instead of once per endpoint.
_cache = {"value": None, "expires_at": 0.0, "refreshing": False}
_cache_lock = threading.Lock()


def _fetch_crm_data():
    with ThreadPoolExecutor(max_workers=2) as executor:
        users_future = executor.submit(fetch_all_users)
        managers_future = executor.submit(fetch_all_managers)
        return {
            "pensioners": users_future.result(),
            "volunteers": managers_future.result(),
            "fetched_at": datetime.now().isoformat(),
        }


def _refresh_cache():
    try:
        data = _fetch_crm_data()
        with _cache_lock:
            _cache["value"] = data
            _cache["expires_at"] = time.time() + CACHE_TTL
        logger.info("Кэш CRM обновлён в фоне")
    except Exception as e:
        logger.error(f"Не удалось обновить кэш CRM: {e}")
    finally:
        with _cache_lock:
            _cache["refreshing"] = False


def _get_crm_data():
    now = time.time()

    with _cache_lock:
        if _cache["value"] is not None:
            # Serve the cached snapshot immediately; if it is stale, refresh
            # it in the background so requests never wait for the CRM.
            if now >= _cache["expires_at"] and not _cache["refreshing"]:
                _cache["refreshing"] = True
                threading.Thread(target=_refresh_cache, daemon=True).start()
            return _cache["value"]

        # First load after startup: block until the data arrives.
        data = _fetch_crm_data()
        _cache["value"] = data
        _cache["expires_at"] = time.time() + CACHE_TTL
        return data


def get_current_metrics():
    try:
        data = _get_crm_data()
        result = {
            "pensioners_count": len(data["pensioners"]),
            "volunteers_count": len(data["volunteers"]),
            "last_updated": data["fetched_at"],
            "status": "active"
        }
        logger.info(
            f"Метрики: пенсионеров {result['pensioners_count']}, "
            f"волонтёров {result['volunteers_count']}"
        )
        return result
    except Exception as e:
        logger.error(f"Ошибка в get_current_metrics: {e}")
        return {
            "pensioners_count": 0,
            "volunteers_count": 0,
            "last_updated": datetime.now().isoformat(),
            "status": f"error: {str(e)}"
        }


def _extract_item_date(item: dict):
    # Try more specific fields first (last login, last activity, etc.)
    priority_fields = [
        "lastLogin", "last_login", "lastActivity", "last_activity",
        "lastUpdate", "last_update", "updatedAt", "updated_at",
        "modifiedAt", "modified_at", "modified", "lastSeen", "last_seen"
    ]

    # Then try creation date fields
    date_fields = [
        "createdAt", "created_at", "dateCreated", "createdDate", "addDate",
        "registrationDate", "regDate", "reg_date", "created_on", "created",
        "date", "date_added", "joined_at", "joinDate"
    ]

    # Try priority fields first (for volunteers with grouped creation dates)
    for field in priority_fields:
        value = item.get(field)
        if not value:
            continue
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(int(value)).date()
            parsed = parse_date(str(value))
            return parsed.date()
        except Exception:
            continue

    # Fall back to creation date fields
    for field in date_fields:
        value = item.get(field)
        if not value:
            continue
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(int(value)).date()
            parsed = parse_date(str(value))
            return parsed.date()
        except Exception:
            continue
    return None


def _build_history_from_items(items: list[dict], days: int):
    today = datetime.now().date()
    start_date = today - timedelta(days=days - 1)

    date_counts = Counter()
    dates_found = 0
    for item in items:
        item_date = _extract_item_date(item)
        if item_date is None:
            continue
        dates_found += 1
        if item_date > today:
            item_date = today
        date_counts[item_date] += 1

    logger.info(f"_build_history_from_items: из {len(items)} элементов найдено дат: {dates_found}")

    if not date_counts:
        logger.warning("Нет дат найдено, будет использована синтетическая генерация")
        return []

    base_count = sum(count for date, count in date_counts.items() if date < start_date)
    history = []
    cumulative = base_count

    for day in range(days):
        current = start_date + timedelta(days=day)
        cumulative += date_counts.get(current, 0)
        history.append({"date": current.strftime("%Y-%m-%d"), "count": cumulative})

    logger.info(f"История построена из реальных дат: {len(history)} дней")
    return history


def _build_historical_series(total_count: int, days: int) -> list[int]:
    if days <= 1:
        return [total_count]

    if days >= 90:
        min_ratio = 0.1
    elif days >= 30:
        min_ratio = 0.2
    else:
        min_ratio = 0.4

    series = []
    for i in range(days):
        progress = i / (days - 1)
        value = int(total_count * (min_ratio + (1 - min_ratio) * (progress ** 1.8)))
        series.append(value)
    return series


def get_history_data(period: str = "30d"):
    try:
        data = _get_crm_data()

        if period == "all":
            days = 365
        else:
            days = int(period[:-1])

        pensioners_history = _build_history_from_items(data["pensioners"], days)
        volunteers_history = _build_history_from_items(data["volunteers"], days)

        if not pensioners_history:
            pensioners_history = [
                {"date": (datetime.now().date() - timedelta(days=days - 1 - idx)).strftime("%Y-%m-%d"),
                 "count": count}
                for idx, count in enumerate(_build_historical_series(len(data["pensioners"]), days))
            ]

        if not volunteers_history:
            volunteers_history = [
                {"date": (datetime.now().date() - timedelta(days=days - 1 - idx)).strftime("%Y-%m-%d"),
                 "count": count}
                for idx, count in enumerate(_build_historical_series(len(data["volunteers"]), days))
            ]

        return {
            "period": period,
            "pensioners": pensioners_history,
            "volunteers": volunteers_history
        }
    except Exception as e:
        logger.error(f"Ошибка в get_history_data: {e}")
        return {
            "period": period,
            "pensioners": [],
            "volunteers": [],
            "error": str(e)
        }
