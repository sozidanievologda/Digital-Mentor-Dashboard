import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env for local development. Environment variables take precedence.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.getenv("MOYKLASS_API_KEY", "")
URL_AUTH = os.getenv("MOYKLASS_AUTH_URL", "https://api.moyklass.com/v1/company/auth/getToken")
USERS_API_URL = os.getenv("MOYKLASS_USERS_URL", "https://api.moyklass.com/v1/company/users")
MANAGERS_API_URL = os.getenv("MOYKLASS_MANAGERS_URL", "https://api.moyklass.com/v1/company/managers")

if not API_KEY:
    raise RuntimeError(
        "MOYKLASS_API_KEY is not set. Copy backend/.env.example to backend/.env "
        "and fill in your CRM API key."
    )
