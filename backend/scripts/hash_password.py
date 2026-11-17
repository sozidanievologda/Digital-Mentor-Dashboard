"""Generate a password hash for DASHBOARD_PASSWORD_HASH.

Usage (from backend/):
    python scripts/hash_password.py
    python scripts/hash_password.py "my password"
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.utils.passwords import hash_password  # noqa: E402


def main():
    password = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Пароль: ")
    if not password:
        print("Пустой пароль недопустим", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
