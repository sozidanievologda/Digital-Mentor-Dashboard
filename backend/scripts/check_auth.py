"""Проверка логина и пароля дашборда.

Сверяет введённые данные с backend/.env и, при желании, с запущенным API.

    cd backend
    python scripts/check_auth.py
    python scripts/check_auth.py --api-url http://localhost:8080/api

Скрипт не печатает пароль и хеш.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from app.security import auth_configured, credentials_valid  # noqa: E402
from app.utils import config  # noqa: E402


def read_password() -> str:
    try:
        value = getpass.getpass("Пароль: ")
    except (EOFError, OSError):
        value = ""
    if value:
        return value
    try:
        return input("Пароль (видимым текстом): ")
    except EOFError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Проверка входа в дашборд")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--api-url", help="например, http://localhost:8080/api")
    args = parser.parse_args()

    username = args.username or os.getenv("DM_USERNAME") or input("Логин: ").strip()
    password = args.password or os.getenv("DM_PASSWORD") or read_password()

    configured = auth_configured()
    username_ok = bool(config.DASHBOARD_USERNAME) and username == config.DASHBOARD_USERNAME
    password_ok = credentials_valid(username, password)
    secret_ok = bool(config.SESSION_SECRET)

    print(f"конфигурация:            {config.BACKEND_DIR / '.env' if (config.BACKEND_DIR / '.env').exists() else 'переменные окружения (Docker/CI)'}")
    print(f"авторизация настроена:   {'да' if configured else 'НЕТ'}")
    print(f"логин совпадает:         {'да' if username_ok else 'НЕТ'}")
    print(f"пароль подходит:         {'да' if password_ok else 'НЕТ'}")
    print(f"SESSION_SECRET задан:    {'да' if secret_ok else 'НЕТ (токены сбрасываются при рестарте)'}")

    if not configured:
        print("\nВ .env нет DASHBOARD_USERNAME и/или DASHBOARD_PASSWORD_HASH.")
        print("Запустите: python scripts/setup_env.py --no-input (с DM_PASSWORD)")
        return 1

    if not (username_ok and password_ok):
        print("\nЛокальный .env не совпадает с введёнными данными.")
        print("Задайте пароль заново:")
        print('  PowerShell: $env:DM_PASSWORD = "..."; python scripts/setup_env.py --no-input')
        print("  Bash:       DM_PASSWORD='...' python scripts/setup_env.py --no-input")
        return 1

    if args.api_url:
        base = args.api_url.rstrip("/")
        try:
            response = requests.post(
                f"{base}/auth/login",
                json={"username": username, "password": password},
                timeout=20,
            )
            print(f"\nAPI /auth/login:        HTTP {response.status_code}")
            if response.ok:
                token = response.json()["access_token"]
                me = requests.get(
                    f"{base}/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=20,
                )
                print(f"API /auth/me:           HTTP {me.status_code}")
                if me.status_code != 200:
                    print("Токен не принимается: проверьте, что запущен один процесс и SESSION_SECRET постоянный.")
                    return 1
            else:
                print("Запущенный бэкенд не принимает эти данные.")
                print("Пересоздайте контейнер: docker compose up -d --force-recreate backend")
                return 1
        except requests.RequestException as exc:
            print(f"\nНе удалось обратиться к API: {exc}")
            return 1

    print("\nРЕЗУЛЬТАТ: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
