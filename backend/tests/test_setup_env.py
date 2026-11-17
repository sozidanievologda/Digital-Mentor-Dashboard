import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.setup_env as setup_env  # noqa: E402
from app.utils.passwords import verify_password  # noqa: E402


def test_upsert_preserves_comments_and_custom_keys():
    text = "# comment\nCUSTOM=keep\nDASHBOARD_PASSWORD=plain\n"
    output = setup_env.upsert_env_lines(
        text,
        {
            "MOYKLASS_API_KEY": "key",
            "DASHBOARD_USERNAME": "analyst",
            "DASHBOARD_PASSWORD_HASH": "hash",
            "SESSION_SECRET": "secret",
        },
    )
    assert "# comment" in output
    assert "CUSTOM=keep" in output
    assert "DASHBOARD_PASSWORD=plain" not in output
    assert "DASHBOARD_PASSWORD_HASH=hash" in output
    assert output.endswith("\n")


def test_upsert_replaces_in_place():
    text = "A=1\nMOYKLASS_API_KEY=old\nB=2\n"
    output = setup_env.upsert_env_lines(text, {"MOYKLASS_API_KEY": "new"})
    assert output.strip().splitlines() == ["A=1", "MOYKLASS_API_KEY=new", "B=2"]


def test_normalize_api_key_strips_paste_noise():
    assert setup_env.normalize_api_key('  "abc123"  ') == "abc123"
    assert setup_env.normalize_api_key("\ufeffabc123\n") == "abc123"
    assert setup_env.normalize_api_key("abc123\nsecond-line") == "abc123"
    assert setup_env.normalize_api_key("   \n") == ""


def test_prompt_api_key_falls_back_to_clipboard(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "")
    monkeypatch.setattr(setup_env, "read_clipboard", lambda: "clip-key")
    assert setup_env.prompt_api_key() == "clip-key"


def test_prompt_api_key_keeps_current_on_empty_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda *_: "")
    monkeypatch.setattr(setup_env, "read_clipboard", lambda: "")
    assert setup_env.prompt_api_key("existing") == "existing"


def test_password_hidden_input(monkeypatch):
    monkeypatch.setattr(setup_env.getpass, "getpass", lambda _: "hidden-pass")
    assert setup_env._prompt_password("Пароль: ") == "hidden-pass"


def test_password_visible_fallback(monkeypatch):
    monkeypatch.setattr(setup_env.getpass, "getpass", lambda _: "")
    answers = iter(["y", "secret123"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    assert setup_env._prompt_password("Пароль: ") == "secret123"


def test_password_fallback_declined(monkeypatch):
    monkeypatch.setattr(setup_env.getpass, "getpass", lambda _: "")
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert setup_env._prompt_password("Пароль: ") == ""


def test_setup_writes_valid_configuration(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "setup_env.py",
            "--env-path",
            str(env_path),
            "--no-input",
            "--api-key",
            "test-key",
            "--username",
            "tester",
            "--password",
            "secret123",
        ],
    )

    assert setup_env.main() == 0
    values = setup_env.read_env(env_path)
    assert values["MOYKLASS_API_KEY"] == "test-key"
    assert values["DASHBOARD_USERNAME"] == "tester"
    assert verify_password("secret123", values["DASHBOARD_PASSWORD_HASH"])
    assert len(values["SESSION_SECRET"]) == 64
    assert "localhost:8080" in values["CORS_ORIGINS"]


def test_setup_keeps_password_hash_and_secret_on_rerun(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "setup_env.py", "--env-path", str(env_path), "--no-input",
            "--api-key", "first", "--username", "tester", "--password", "secret123",
        ],
    )
    assert setup_env.main() == 0
    first = setup_env.read_env(env_path)

    monkeypatch.setattr(
        sys,
        "argv",
        ["setup_env.py", "--env-path", str(env_path), "--no-input", "--api-key", "second"],
    )
    assert setup_env.main() == 0
    second = setup_env.read_env(env_path)

    assert second["MOYKLASS_API_KEY"] == "second"
    assert second["DASHBOARD_PASSWORD_HASH"] == first["DASHBOARD_PASSWORD_HASH"]
    assert second["SESSION_SECRET"] == first["SESSION_SECRET"]


def test_setup_requires_password_without_input(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(
        sys,
        "argv",
        ["setup_env.py", "--env-path", str(env_path), "--no-input", "--api-key", "key"],
    )
    with pytest.raises(SystemExit):
        setup_env.main()
