import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env for local development. Environment variables take precedence.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _text(name, default=""):
    return os.getenv(name, default).strip()


BACKEND_DIR = Path(__file__).resolve().parents[2]

# CRM "MoyKlass"
API_KEY = _text("MOYKLASS_API_KEY")
URL_AUTH = _text("MOYKLASS_AUTH_URL", "https://api.moyklass.com/v1/company/auth/getToken")
USERS_API_URL = _text("MOYKLASS_USERS_URL", "https://api.moyklass.com/v1/company/users")
MANAGERS_API_URL = _text("MOYKLASS_MANAGERS_URL", "https://api.moyklass.com/v1/company/managers")

if not API_KEY:
    raise RuntimeError(
        "MOYKLASS_API_KEY is not set. Copy backend/.env.example to backend/.env "
        "and fill in your CRM API key."
    )

# Dashboard auth (single analyst account)
DASHBOARD_USERNAME = _text("DASHBOARD_USERNAME")
DASHBOARD_PASSWORD_HASH = _text("DASHBOARD_PASSWORD_HASH")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")  # development fallback only
SESSION_SECRET = _text("SESSION_SECRET")
SESSION_TTL_SECONDS = int(_text("SESSION_TTL_SECONDS", "43200"))  # 12 hours

# Storage and refresh
DATABASE_PATH = Path(_text("DATABASE_PATH", str(BACKEND_DIR / "data" / "dashboard.db")))
REFRESH_INTERVAL_SECONDS = int(_text("REFRESH_INTERVAL_SECONDS", "3600"))
DATA_TTL_SECONDS = int(_text("DATA_TTL_SECONDS", "3600"))

# Project participants are users tagged with "ФПГ_ЦН ..." in the CRM.
PROJECT_TAG_PREFIX = _text("PROJECT_TAG_PREFIX", "ФПГ_ЦН")
PROJECT_TAG_NAMES = [name.strip() for name in _text("PROJECT_TAG_NAMES").split(",") if name.strip()]
PROJECT_START_DATE = _text("PROJECT_START_DATE", "2025-02-01")
