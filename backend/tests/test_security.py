from app.security import auth_configured, credentials_valid
from app.utils import config
from app.utils.passwords import hash_password


def configure(monkeypatch, username="analyst", password_hash=None, plain=""):
    monkeypatch.setattr(config, "DASHBOARD_USERNAME", username)
    monkeypatch.setattr(config, "DASHBOARD_PASSWORD_HASH", password_hash or "")
    monkeypatch.setattr(config, "DASHBOARD_PASSWORD", plain)


def test_credentials_valid_with_hash(monkeypatch):
    configure(monkeypatch, password_hash=hash_password("secret123"))
    assert auth_configured()
    assert credentials_valid("analyst", "secret123")
    assert not credentials_valid("analyst", "wrong")
    assert not credentials_valid("Analyst", "secret123")


def test_credentials_valid_with_plaintext_fallback(monkeypatch):
    configure(monkeypatch, plain="dev-password")
    assert credentials_valid("analyst", "dev-password")
    assert not credentials_valid("analyst", "other")


def test_auth_not_configured(monkeypatch):
    configure(monkeypatch, username="", plain="")
    assert not auth_configured()
    assert not credentials_valid("analyst", "secret123")
