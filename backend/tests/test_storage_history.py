from datetime import date

from app.services import collector, storage


def test_cumulative_counts_counts_records_before_range():
    created = [
        "2025-01-01T10:00:00+00:00",
        "2025-01-03T10:00:00+00:00",
        "2025-01-03T12:00:00+00:00",
        "2025-01-05T10:00:00+00:00",
    ]
    result = collector._cumulative_counts(created, date(2025, 1, 2), date(2025, 1, 4))
    assert result[date(2025, 1, 2)] == 1
    assert result[date(2025, 1, 3)] == 3
    assert result[date(2025, 1, 4)] == 3


def test_storage_keeps_project_flag():
    users = [
        {
            "id": 1,
            "createdAt": "2025-03-01T00:00:00+00:00",
            "tags": [{"id": 10, "name": "ФПГ_ЦН Консультации"}],
        },
        {
            "id": 2,
            "createdAt": "2025-04-01T00:00:00+00:00",
            "tags": [{"id": 11, "name": "Другой тег"}],
        },
    ]
    storage.replace_users(users, {1})
    assert storage.get_project_created_dates() == ["2025-03-01T00:00:00+00:00"]


def test_series_fills_missing_days():
    from app.services.data_processing import _build_series

    storage.upsert_snapshot("2026-01-01", "2026-01-01T10:00:00", 5, 10, 2, source="live")
    storage.upsert_snapshot("2026-01-03", "2026-01-03T10:00:00", 7, 12, 2, source="live")

    pensioners, volunteers, approximate = _build_series(date(2026, 1, 1), date(2026, 1, 3))

    assert [point["count"] for point in pensioners] == [5, 5, 7]
    assert [point["count"] for point in volunteers] == [2, 2, 2]
    assert approximate is False


def test_series_marks_backfilled_ranges():
    from app.services.data_processing import _build_series

    storage.upsert_snapshot("2026-02-01", "2026-02-01T00:00:00", 5, 10, 2, source="backfill")
    _, _, approximate = _build_series(date(2026, 2, 1), date(2026, 2, 1))
    assert approximate is True
