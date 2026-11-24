import logging
from collections import Counter
from datetime import date, timedelta

from fastapi import HTTPException, status

from ..utils import config
from . import collector, storage

logger = logging.getLogger(__name__)

MAX_HISTORY_DAYS = 730
PERIOD_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "quarter": 90,
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
}


def _parse_day(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректная дата в параметре {field_name}: {value}",
        )


def list_project_tags():
    return collector.project_tags()


def _parse_tag_selection(raw):
    """Return (tag_ids, all_selected, tags).

    None means "all project tags"; an empty string means "nothing selected".
    """
    project = collector.project_tags()
    by_id = {tag["id"]: tag for tag in project}

    if raw is None:
        return list(by_id), True, project
    if not raw.strip():
        return [], False, []

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    try:
        ids = [int(part) for part in parts]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tags должен содержать id тегов через запятую",
        )

    unknown = sorted(set(ids) - set(by_id))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестные теги проекта: {unknown}",
        )

    unique_ids = list(dict.fromkeys(ids))
    all_selected = set(unique_ids) == set(by_id)
    return unique_ids, all_selected, [by_id[tag_id] for tag_id in unique_ids]


def get_tags_data():
    tags = collector.project_tags()
    total = storage.count_users_for_tags([tag["id"] for tag in tags])
    return {"tags": tags, "unique_users": total}


def get_current_metrics(tags_raw=None):
    tag_ids, all_selected, selected_tags = _parse_tag_selection(tags_raw)
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
    pensioners_count = storage.count_users_for_tags(tag_ids) if tag_ids else 0

    return {
        "pensioners_count": pensioners_count,
        "volunteers_count": snapshot["volunteers"],
        "total_users": snapshot["total_users"],
        "last_updated": snapshot["taken_at"],
        "last_success_at": last_success_at,
        "status": "active" if data_status == "live" else "stale",
        "data_status": data_status,
        "error": last_error,
        "selected_tag_ids": tag_ids,
        "selected_tags": [tag["name"] for tag in selected_tags],
        "all_tags_selected": all_selected,
    }


def refresh_and_get_metrics(tags_raw=None):
    try:
        collector.refresh_data(blocking=True)
    except Exception as exc:
        logger.warning(f"Ручное обновление не удалось: {exc}")
    return get_current_metrics(tags_raw=tags_raw)


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
                    detail="period должен быть одним из: 7d, 30d, 90d, quarter, 1m, 3m, 6m, 12m, all",
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


def _month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)


def _shift_months(day: date, months: int) -> date:
    total = day.year * 12 + (day.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _cumulative_at(rows, baseline, day: date):
    pensioners = baseline["project_users"] if baseline else None
    volunteers = baseline["volunteers"] if baseline else None
    for row in rows:
        if row["snapshot_date"] <= day.isoformat():
            pensioners = row["project_users"]
            volunteers = row["volunteers"]
        else:
            break
    return pensioners, volunteers


def _build_monthly_series(start_date: date, end_date: date):
    """Monthly growth: how many new participants appeared in each month.

    Buckets follow the requested range: the first and last month may be
    partial if the range does not start/end on a month boundary.
    """
    rows = storage.get_snapshots(start_date.isoformat(), end_date.isoformat())
    baseline = storage.get_snapshot_before(start_date.isoformat())
    approximate = any(row["source"] == "backfill" for row in rows + ([baseline] if baseline else []))

    previous_pensioners = baseline["project_users"] if baseline else None
    previous_volunteers = baseline["volunteers"] if baseline else None
    pensioners_series = []
    volunteers_series = []

    cursor = _month_start(start_date)
    while cursor <= end_date:
        month_end = min(_next_month(cursor) - timedelta(days=1), end_date)
        pensioners, volunteers = _cumulative_at(rows, baseline, month_end)

        pensioners_series.append({
            "date": cursor.strftime("%Y-%m"),
            "count": None if pensioners is None or previous_pensioners is None
            else pensioners - previous_pensioners,
        })
        volunteers_series.append({
            "date": cursor.strftime("%Y-%m"),
            "count": None if volunteers is None or previous_volunteers is None
            else volunteers - previous_volunteers,
        })

        previous_pensioners = pensioners
        previous_volunteers = volunteers
        cursor = _next_month(cursor)

    return pensioners_series, volunteers_series, approximate


def _parse_created_days(values):
    days = []
    for value in values:
        try:
            days.append(date.fromisoformat(str(value)[:10]))
        except (ValueError, TypeError):
            continue
    return days


def _build_dates_cumulative(created, start_date: date, end_date: date):
    days = _parse_created_days(created)
    per_day = Counter(day.isoformat() for day in days)
    current = sum(1 for day in days if day < start_date)

    series = []
    cursor = start_date
    while cursor <= end_date:
        current += per_day.get(cursor.isoformat(), 0)
        series.append({"date": cursor.isoformat(), "count": current})
        cursor += timedelta(days=1)
    return series


def _build_dates_monthly(created, start_date: date, end_date: date):
    days = _parse_created_days(created)
    previous = sum(1 for day in days if day < start_date)

    series = []
    cursor = _month_start(start_date)
    while cursor <= end_date:
        month_end = min(_next_month(cursor) - timedelta(days=1), end_date)
        value = sum(1 for day in days if day <= month_end)
        series.append({"date": cursor.strftime("%Y-%m"), "count": value - previous})
        previous = value
        cursor = _next_month(cursor)
    return series


def get_history_data(period: str = "30d", start: str = None, end: str = None,
                     group: str = "day", tags_raw=None):
    if group not in ("day", "month"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="group должен быть day или month",
        )

    tag_ids, all_selected, selected_tags = _parse_tag_selection(tags_raw)
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

    if group == "month" and not start and not end:
        # Calendar-month periods (1m, 3m, 6m, 12m) start on the first day of
        # the month so the columns are whole months.
        period_months = period[:-1]
        if period.endswith("m") and period_months.isdigit():
            start_date = _shift_months(_month_start(end_date), -(int(period_months) - 1))

    source = "snapshots"
    if all_selected:
        if group == "month":
            pensioners, volunteers, approximate = _build_monthly_series(start_date, end_date)
        else:
            pensioners, volunteers, approximate = _build_series(start_date, end_date)
    else:
        # Tag subsets have no historical snapshots: approximate the series
        # from the users' CRM creation dates.
        created = storage.get_created_dates_for_tags(tag_ids)
        approximate = True
        source = "tags"
        if group == "month":
            pensioners = _build_dates_monthly(created, start_date, end_date)
            _, volunteers, _ = _build_monthly_series(start_date, end_date)
        else:
            pensioners = _build_dates_cumulative(created, start_date, end_date)
            _, volunteers, _ = _build_series(start_date, end_date)

    return {
        "period": period,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "group": group,
        "source": source,
        "approximate": approximate,
        "pensioners": pensioners,
        "volunteers": volunteers,
        "selected_tag_ids": tag_ids,
        "all_tags_selected": all_selected,
        "selected_tags": [tag["name"] for tag in selected_tags],
    }
