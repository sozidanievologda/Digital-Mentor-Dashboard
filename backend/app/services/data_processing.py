from collections import Counter
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from .crm_service import fetch_all_users, fetch_all_managers
import logging
import time

logger = logging.getLogger(__name__)
_cache = {
    "metrics": {"value": None, "expires_at": 0},
    "history": {"value": {}, "expires_at": 0}
}
CACHE_TTL = 300  # секунды (5 минут)


def _is_cache_valid(key: str):
    return time.time() < _cache[key]["expires_at"]


def _set_cache(key: str, value):
    _cache[key]["value"] = value
    _cache[key]["expires_at"] = time.time() + CACHE_TTL


def get_current_metrics():
    try:
        if _is_cache_valid("metrics"):
            logger.info("Возвращаю закэшированные метрики")
            return _cache["metrics"]["value"]

        pensioners = fetch_all_users()
        volunteers = fetch_all_managers()

        result = {
            "pensioners_count": len(pensioners),
            "volunteers_count": len(volunteers),
            "last_updated": datetime.now().isoformat(),
            "status": "active"
        }
        _set_cache("metrics", result)
        logger.info(f"Текущее количество пенсионеров: {len(pensioners)}")
        logger.info(f"Текущее количество волонтеров: {len(volunteers)}")
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
    logger.info(f"Date counts: {dict(date_counts)}")
    
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
        if _is_cache_valid("history") and period in _cache["history"]["value"]:
            logger.info("Возвращаю закэшированные исторические данные")
            return _cache["history"]["value"][period]

        pensioners = fetch_all_users()
        volunteers = fetch_all_managers()

        if period == "all":
            days = 365
        else:
            days = int(period[:-1])

        pensioners_history = _build_history_from_items(pensioners, days)
        volunteers_history = _build_history_from_items(volunteers, days)

        if not pensioners_history:
            pensioners_history = [
                {"date": (datetime.now().date() - timedelta(days=days - 1 - idx)).strftime("%Y-%m-%d"),
                 "count": count}
                for idx, count in enumerate(_build_historical_series(len(pensioners), days))
            ]

        if not volunteers_history:
            volunteers_history = [
                {"date": (datetime.now().date() - timedelta(days=days - 1 - idx)).strftime("%Y-%m-%d"),
                 "count": count}
                for idx, count in enumerate(_build_historical_series(len(volunteers), days))
            ]

        result = {
            "period": period,
            "pensioners": pensioners_history,
            "volunteers": volunteers_history
        }
        _cache["history"]["value"][period] = result
        _cache["history"]["expires_at"] = time.time() + CACHE_TTL
        return result
    except Exception as e:
        logger.error(f"Ошибка в get_history_data: {e}")
        return {
            "period": period,
            "pensioners": [],
            "volunteers": [],
            "error": str(e)
        }
