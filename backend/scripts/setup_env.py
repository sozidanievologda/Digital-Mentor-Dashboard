"""Заполняет backend/.env всем необходимым.

Генерирует SESSION_SECRET и DASHBOARD_PASSWORD_HASH, сохраняет существующие
значения при повторном запуске и не печатает секреты в вывод.

Интерактивно:
    python backend/scripts/setup_env.py

Без вопросов (для автоматизации):
    DM_API_KEY=... DM_USERNAME=analyst DM_PASSWORD=... \
        python backend/scripts/setup_env.py --no-input
"""

import argparse
import getpass
import os
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.utils.passwords import hash_password  # noqa: E402

DEFAULT_ENV_PATH = BACKEND_DIR / ".env"

MANAGED_KEYS = [
    "MOYKLASS_API_KEY",
    "MOYKLASS_AUTH_URL",
    "MOYKLASS_USERS_URL",
    "MOYKLASS_MANAGERS_URL",
    "DASHBOARD_USERNAME",
    "DASHBOARD_PASSWORD_HASH",
    "SESSION_SECRET",
    "SESSION_TTL_SECONDS",
    "CORS_ORIGINS",
    "REFRESH_INTERVAL_SECONDS",
    "DATA_TTL_SECONDS",
    "PROJECT_TAG_PREFIX",
    "PROJECT_START_DATE",
]

DEFAULTS = {
    "MOYKLASS_AUTH_URL": "https://api.moyklass.com/v1/company/auth/getToken",
    "MOYKLASS_USERS_URL": "https://api.moyklass.com/v1/company/users",
    "MOYKLASS_MANAGERS_URL": "https://api.moyklass.com/v1/company/managers",
    "SESSION_TTL_SECONDS": "43200",
    "CORS_ORIGINS": "http://localhost:8080,http://localhost:8000,null",
    "REFRESH_INTERVAL_SECONDS": "3600",
    "DATA_TTL_SECONDS": "3600",
    "PROJECT_TAG_PREFIX": "ФПГ_ЦН",
    "PROJECT_START_DATE": "2025-02-01",
}


def read_env(path: Path) -> dict:
    path = Path(path)
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def upsert_env_lines(existing_text: str, values: dict) -> str:
    """Replace managed keys in place and append the missing ones."""
    lines = existing_text.splitlines() if existing_text else []
    remaining = dict(values)
    result = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                result.append(f"{key}={remaining.pop(key)}")
                continue
            if key == "DASHBOARD_PASSWORD" and "DASHBOARD_PASSWORD_HASH" in values:
                # Never keep the plaintext password when a hash is available.
                continue
        result.append(line)

    if remaining:
        if result and result[-1].strip():
            result.append("")
        result.extend(f"{key}={value}" for key, value in remaining.items())

    return "\n".join(result) + "\n"


def mask_secret(value: str) -> str:
    if not value:
        return "не задан"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}…{value[-4:]}"


def _prompt(label, default=None, secret=False):
    hint = f" [{default}]" if default else ""
    if secret:
        value = getpass.getpass(f"{label}{hint}: ").strip()
    else:
        value = input(f"{label}{hint}: ").strip()
    return value or default


def main():
    parser = argparse.ArgumentParser(description="Настройка backend/.env")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--api-key")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--no-input", action="store_true")
    parser.add_argument("--rotate-session-secret", action="store_true")
    args = parser.parse_args()

    env_path = Path(args.env_path).expanduser()
    existing = read_env(env_path)
    interactive = not args.no_input and sys.stdin.isatty()

    api_key = args.api_key or os.getenv("DM_API_KEY") or existing.get("MOYKLASS_API_KEY")
    if api_key and interactive and not (args.api_key or os.getenv("DM_API_KEY")):
        entered = getpass.getpass(
            f"API-ключ «МойКласс» уже задан ({mask_secret(api_key)}), Enter — оставить: "
        ).strip()
        if entered:
            api_key = entered
    elif not api_key:
        if not interactive:
            parser.error("не задан API-ключ: используйте --api-key или DM_API_KEY")
        api_key = getpass.getpass("API-ключ «МойКласс»: ").strip()
    if not api_key:
        parser.error("API-ключ обязателен")

    username = (
        args.username
        or os.getenv("DM_USERNAME")
        or existing.get("DASHBOARD_USERNAME")
        or "analyst"
    )
    if interactive and not (args.username or os.getenv("DM_USERNAME")):
        username = _prompt("Логин для дашборда", default=username) or username

    password = args.password or os.getenv("DM_PASSWORD")
    password_hash = existing.get("DASHBOARD_PASSWORD_HASH")
    if password:
        password_hash = hash_password(password)
    elif password_hash and interactive:
        entered = getpass.getpass("Новый пароль (Enter — оставить прежний): ")
        if entered:
            password = entered
            if len(password) < 8:
                parser.error("пароль должен быть не короче 8 символов")
            password_hash = hash_password(password)
    elif not password_hash:
        if not interactive:
            parser.error("не задан пароль: используйте --password или DM_PASSWORD")
        while True:
            password = getpass.getpass("Пароль для дашборда: ")
            if len(password) < 8:
                print("Пароль должен быть не короче 8 символов")
                continue
            if password != getpass.getpass("Повторите пароль: "):
                print("Пароли не совпадают")
                continue
            password_hash = hash_password(password)
            break

    session_secret = None if args.rotate_session_secret else existing.get("SESSION_SECRET")
    generated_secret = not session_secret
    if not session_secret:
        session_secret = secrets.token_hex(32)

    merged = {
        **DEFAULTS,
        **{key: existing[key] for key in MANAGED_KEYS if key in existing},
        "MOYKLASS_API_KEY": api_key,
        "DASHBOARD_USERNAME": username,
        "DASHBOARD_PASSWORD_HASH": password_hash,
        "SESSION_SECRET": session_secret,
    }
    values = {key: merged[key] for key in MANAGED_KEYS if key in merged}

    existing_text = env_path.read_text(encoding="utf-8") if env_path.exists() else (
        "# Локальная конфигурация дашборда. Не коммитится в git.\n"
    )
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(upsert_env_lines(existing_text, values), encoding="utf-8")
    if os.name == "posix":
        env_path.chmod(0o600)

    print(f"\nКонфигурация записана: {env_path}")
    print(f"  API-ключ:        {mask_secret(api_key)}")
    print(f"  Логин:           {username}")
    print(f"  Пароль:          {'новый хеш' if password else 'сохранён прежний хеш'}")
    print(f"  SESSION_SECRET:  {'сгенерирован' if generated_secret else 'сохранён'}")
    print(f"  CORS:            {values['CORS_ORIGINS']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
