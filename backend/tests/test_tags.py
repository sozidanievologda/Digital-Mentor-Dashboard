from datetime import date

import pytest
from fastapi import HTTPException

from app.services import collector, data_processing, storage


def seed_users():
    users = [
        {
            "id": 1,
            "createdAt": "2026-01-10T00:00:00+00:00",
            "tags": [{"id": 10, "name": "ФПГ_ЦН Тег A"}],
        },
        {
            "id": 2,
            "createdAt": "2026-02-10T00:00:00+00:00",
            "tags": [{"id": 10, "name": "ФПГ_ЦН Тег A"}, {"id": 11, "name": "ФПГ_ЦН Тег B"}],
        },
        {
            "id": 3,
            "createdAt": "2026-02-20T00:00:00+00:00",
            "tags": [{"id": 11, "name": "ФПГ_ЦН Тег B"}],
        },
        {
            "id": 4,
            "createdAt": "2026-02-21T00:00:00+00:00",
            "tags": [{"id": 12, "name": "Другой тег"}],
        },
    ]
    storage.replace_users(users, {1, 2, 3})
    storage.upsert_snapshot("2026-02-28", "2026-02-28T00:00:00", 3, 4, 1, source="live")
    return users


def test_project_tags_are_loaded_from_database():
    seed_users()
    tags = {tag["name"]: tag for tag in collector.project_tags()}
    assert set(tags) == {"ФПГ_ЦН Тег A", "ФПГ_ЦН Тег B"}
    assert tags["ФПГ_ЦН Тег A"]["users"] == 2


def test_tag_counts_are_unique_across_intersections():
    seed_users()
    tags = {tag["name"]: tag["id"] for tag in collector.project_tags()}
    assert storage.count_users_for_tags([tags["ФПГ_ЦН Тег A"]]) == 2
    assert storage.count_users_for_tags([tags["ФПГ_ЦН Тег B"]]) == 2
    assert storage.count_users_for_tags(list(tags.values())) == 3


def test_parse_tag_selection(monkeypatch):
    seed_users()
    tag_ids = [tag["id"] for tag in collector.project_tags()]

    selected, all_selected, _ = data_processing._parse_tag_selection(None)
    assert selected == tag_ids
    assert all_selected is True

    selected, all_selected, _ = data_processing._parse_tag_selection("")
    assert selected == []
    assert all_selected is False

    selected, all_selected, _ = data_processing._parse_tag_selection(str(tag_ids[0]))
    assert selected == [tag_ids[0]]
    assert all_selected is False

    selected, all_selected, _ = data_processing._parse_tag_selection(",".join(map(str, tag_ids)))
    assert selected == tag_ids
    assert all_selected is True

    with pytest.raises(HTTPException):
        data_processing._parse_tag_selection("999999")


def test_metrics_respect_selected_tags(monkeypatch):
    seed_users()
    monkeypatch.setattr(collector, "get_data_status", lambda: "live")
    tag_ids = {tag["name"]: tag["id"] for tag in collector.project_tags()}

    all_metrics = data_processing.get_current_metrics()
    assert all_metrics["pensioners_count"] == 3
    assert all_metrics["all_tags_selected"] is True

    only_a = data_processing.get_current_metrics(tags_raw=str(tag_ids["ФПГ_ЦН Тег A"]))
    assert only_a["pensioners_count"] == 2
    assert only_a["all_tags_selected"] is False

    both = data_processing.get_current_metrics(tags_raw="")
    assert both["pensioners_count"] == 0


def test_tag_history_is_built_from_creation_dates(monkeypatch):
    seed_users()
    monkeypatch.setattr(collector, "ensure_fresh", lambda: None)
    tag_a = next(tag["id"] for tag in collector.project_tags() if tag["name"] == "ФПГ_ЦН Тег A")

    data = data_processing.get_history_data(
        period="custom",
        start="2026-01-01",
        end="2026-02-28",
        group="day",
        tags_raw=str(tag_a),
    )

    assert data["source"] == "tags"
    assert data["approximate"] is True
    assert data["pensioners"][0] == {"date": "2026-01-01", "count": 0}
    assert data["pensioners"][-1] == {"date": "2026-02-28", "count": 2}
    assert data["selected_tag_ids"] == [tag_a]


def test_tag_monthly_history_uses_partial_months(monkeypatch):
    seed_users()
    monkeypatch.setattr(collector, "ensure_fresh", lambda: None)
    tag_b = next(tag["id"] for tag in collector.project_tags() if tag["name"] == "ФПГ_ЦН Тег B")

    data = data_processing.get_history_data(
        period="custom",
        start="2026-02-15",
        end="2026-02-28",
        group="month",
        tags_raw=str(tag_b),
    )

    assert data["pensioners"] == [{"date": "2026-02", "count": 1}]


def test_dates_series_baseline():
    created = [
        "2025-12-31T00:00:00",
        "2026-01-02T00:00:00",
        "2026-01-02T12:00:00",
        "2026-02-01T00:00:00",
    ]
    daily = data_processing._build_dates_cumulative(
        created, date(2026, 1, 1), date(2026, 1, 3)
    )
    assert [point["count"] for point in daily] == [1, 3, 3]

    monthly = data_processing._build_dates_monthly(
        created, date(2026, 1, 1), date(2026, 2, 10)
    )
    assert [point["count"] for point in monthly] == [2, 1]
