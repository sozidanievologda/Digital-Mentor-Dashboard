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
import subprocess
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


def normalize_api_key(value: str) -> str:
    """Trim whitespace, newlines, BOM and wrapping quotes from a pasted key."""
    if not value:
        return ""
    lines = [line for line in value.strip().splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[0].strip().lstrip("\ufeff").strip('"').strip("'").strip()


def read_clipboard() -> str:
    """Best-effort clipboard read without external dependencies."""
    try:
        if os.name == "nt":
            import ctypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if not user32.OpenClipboard(None):
                return ""
            try:
                handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
                if not handle:
                    return ""
                pointer = kernel32.GlobalLock(handle)
                if not pointer:
                    return ""
                try:
                    return ctypes.wstring_at(pointer)
                finally:
                    kernel32.GlobalUnlock(handle)
            finally:
                user32.CloseClipboard()

        if sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return result.stdout if result.returncode == 0 else ""

        for command in (
            ["wl-paste", "--no-newline"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["xsel", "--clipboard", "--output"],
        ):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            except FileNotFoundError:
                continue
            if result.returncode == 0:
                return result.stdout
    except Exception:
        return ""
    return ""


def _safe_input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        raise SystemExit("Ввод прерван")


def _prompt_password(label: str) -> str:
    try:
        value = getpass.getpass(label)
    except (EOFError, OSError):
        value = ""
    if value:
        return value

    # getpass reads character by character and may swallow pasted text on
    # Windows. Offer a visible fallback where Ctrl+V works.
    answer = _safe_input(
        "Скрытый ввод недоступен или пуст. Ввести видимым текстом? [y/N]: "
    ).strip().lower()
    if answer in ("y", "yes", "д", "да"):
        return _safe_input("Пароль: ")
    return ""


def prompt_api_key(current: str = "") -> str:
    while True:
        if current:
            label = (
                f"API-ключ «МойКласс» уже задан ({mask_secret(current)}). "
                "Enter — оставить, или вставьте новый: "
            )
        else:
            label = (
                "API-ключ «МойКласс» (Ctrl+V / правый клик; "
                "Enter — взять из буфера обмена): "
            )
        entered = normalize_api_key(_safe_input(label))
        if not entered:
            entered = normalize_api_key(read_clipboard())
            if entered:
                print(f"Ключ взят из буфера обмена: {mask_secret(entered)}")
        if entered:
            return entered
        if current:
            return current
        print("Ключ не введён, попробуйте ещё раз.")


def _prompt(label, default=None):
    hint = f" [{default}]" if default else ""
    value = _safe_input(f"{label}{hint}: ").strip()
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
    if interactive and not (args.api_key or os.getenv("DM_API_KEY")):
        api_key = prompt_api_key(api_key or "")
    elif not api_key:
        if not interactive:
            parser.error("не задан API-ключ: используйте --api-key или DM_API_KEY")
        api_key = prompt_api_key()
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
        entered = _prompt_password("Новый пароль (Enter — оставить прежний): ")
        if entered:
            password = entered
            if len(password) < 8:
                parser.error("пароль должен быть не короче 8 символов")
            password_hash = hash_password(password)
    elif not password_hash:
        if not interactive:
            parser.error("не задан пароль: используйте --password или DM_PASSWORD")
        while True:
            password = _prompt_password("Пароль для дашборда: ")
            if len(password) < 8:
                print("Пароль должен быть не короче 8 символов")
                continue
            if password != _prompt_password("Повторите пароль: "):
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
