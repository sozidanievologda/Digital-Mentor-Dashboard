from app.services import collector
from app.utils import config


def make_user(user_id, tag_names):
    return {
        "id": user_id,
        "tags": [{"id": index, "name": name} for index, name in enumerate(tag_names)],
    }


def test_project_users_match_prefix():
    users = [
        make_user(1, ["ФПГ_ЦН Консультации"]),
        make_user(2, ["ФПГ Пенсионеры Вологды"]),
        make_user(3, ["Важный", "ФПГ_ЦН Мастер-класс по ИИ"]),
        make_user(4, []),
    ]
    assert collector.project_user_ids(users) == {1, 3}


def test_project_users_with_exact_allowlist(monkeypatch):
    monkeypatch.setattr(config, "PROJECT_TAG_NAMES", ["ФПГ_ЦН Мастер-класс по ИИ"])
    users = [
        make_user(1, ["ФПГ_ЦН Консультации"]),
        make_user(2, ["ФПГ_ЦН Мастер-класс по ИИ"]),
    ]
    assert collector.project_user_ids(users) == {2}


def test_prefix_does_not_match_similar_names(monkeypatch):
    monkeypatch.setattr(config, "PROJECT_TAG_NAMES", [])
    monkeypatch.setattr(config, "PROJECT_TAG_PREFIX", "ФПГ_ЦН")
    users = [
        make_user(1, ["ФПГXЦН чужой тег"]),
        make_user(2, ["ФПГ_ЦН Консультации"]),
    ]
    assert collector.project_user_ids(users) == {2}
