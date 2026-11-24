"""Сверка данных дашборда с CRM «МойКласс» для приёмки.

Сравнивает последний снимок в SQLite с текущей выгрузкой из CRM:
участников проекта, всего пользователей и волонтёров.

Запуск (из backend/, с активированным venv):
    python scripts/verify_metrics.py
    python scripts/verify_metrics.py --details

Код возврата: 0 — совпало, 1 — расхождение, 2 — ошибка.
Вывод не содержит персональных данных.
"""

import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import collector, storage  # noqa: E402
from app.services.crm_service import fetch_all_managers, fetch_all_users  # noqa: E402


def count_tags(users):
    counts = Counter()
    for user in users:
        seen = set()
        for tag in user.get("tags") or []:
            if not isinstance(tag, dict):
                continue
            name = tag.get("name", "")
            if name in seen or not collector.tag_matches(name):
                continue
            seen.add(name)
            counts[name] += 1
    return counts


def main():
    parser = argparse.ArgumentParser(description="Сверка дашборда с CRM")
    parser.add_argument("--details", action="store_true", help="показать разбивку по тегам")
    args = parser.parse_args()

    snapshot = storage.get_latest_snapshot()
    if snapshot is None:
        print("ОШИБКА: в базе нет снимков. Запустите бэкенд и дождитесь загрузки.")
        return 2

    try:
        users = fetch_all_users()
        managers = fetch_all_managers()
    except Exception as exc:
        print(f"ОШИБКА: не удалось получить данные из CRM: {exc}")
        return 2

    project_ids = collector.project_user_ids(users)
    crm = {
        "project": len(project_ids),
        "total": len(users),
        "volunteers": len(managers),
    }
    db = {
        "project": snapshot["project_users"],
        "total": snapshot["total_users"],
        "volunteers": snapshot["volunteers"],
    }

    try:
        age = (datetime.now() - datetime.fromisoformat(snapshot["taken_at"])).total_seconds()
    except ValueError:
        age = None

    print("CRM «МойКласс»:")
    print(f"  участников проекта: {crm['project']}")
    print(f"  всего пользователей: {crm['total']}")
    print(f"  волонтёров: {crm['volunteers']}")
    print("Последний снимок дашборда:")
    print(f"  время: {snapshot['taken_at']} (источник: {snapshot['source']})")
    print(f"  участников проекта: {db['project']}")
    print(f"  всего пользователей: {db['total']}")
    print(f"  волонтёров: {db['volunteers']}")
    if age is not None:
        print(f"  возраст снимка: {age / 60:.1f} мин")

    if args.details:
        print("\nУчастники по тегам проекта:")
        for name, count in count_tags(users).most_common():
            print(f"  {count:4d}  {name}")

    mismatches = [key for key in ("project", "total", "volunteers") if crm[key] != db[key]]
    if mismatches:
        print(f"\nРЕЗУЛЬТАТ: РАСХОЖДЕНИЕ по полям: {', '.join(mismatches)}")
        print("Обновите данные кнопкой «Обновить» или дождитесь фоновой синхронизации.")
        return 1

    print("\nРЕЗУЛЬТАТ: OK — данные дашборда совпадают с CRM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
