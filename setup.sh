#!/usr/bin/env bash
# Настройка и запуск дашборда на Linux/macOS.
#   ./setup.sh              — заполнить backend/.env и запустить (Docker или локально)
#   ./setup.sh --no-start   — только настроить
#   ./setup.sh --local      — запустить локально через uvicorn
#   ./setup.sh --docker     — запустить через Docker Compose
set -euo pipefail
cd "$(dirname "$0")"

NO_START=0
MODE="auto"
ARGS=()

for arg in "$@"; do
    case "$arg" in
        --no-start) NO_START=1 ;;
        --docker) MODE="docker" ;;
        --local) MODE="local" ;;
        *) ARGS+=("$arg") ;;
    esac
done

docker_ready() {
    command -v docker >/dev/null 2>&1 || return 1
    docker info >/dev/null 2>&1 || return 1
    docker compose version >/dev/null 2>&1 || return 1
}

find_python() {
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 \
            && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}

PYTHON="$(find_python || true)"

echo "== Настройка Digital Mentor Dashboard =="

if [ -n "$PYTHON" ]; then
    "$PYTHON" backend/scripts/setup_env.py "${ARGS[@]}"
elif docker_ready; then
    echo "Python не найден — настраиваю .env через контейнер python:3.12-slim"
    TTY_FLAGS=()
    [ -t 0 ] && TTY_FLAGS=(-it)
    docker run --rm "${TTY_FLAGS[@]}" --user "$(id -u):$(id -g)" \
        -v "$PWD/backend:/app" -w /app \
        python:3.12-slim python scripts/setup_env.py "${ARGS[@]}"
else
    echo "Нужен Python 3.11+ (или Docker). Установите, например: sudo apt install python3 python3-venv"
    exit 1
fi

if [ "$NO_START" = "1" ]; then
    echo
    echo "Готово. Запуск:"
    echo "  Docker:      docker compose up -d --build"
    echo "  Локально:    cd backend && ./.venv/bin/python -m uvicorn app.main:app --port 8000"
    exit 0
fi

if [ "$MODE" != "local" ] && docker_ready; then
    echo
    echo "== Запуск через Docker =="
    docker compose up -d --build
    echo
    echo "Дашборд: http://localhost:8080"
    echo "Логи:    docker compose logs -f backend"
    exit 0
fi

if [ "$MODE" = "docker" ]; then
    echo "Docker не запущен или нет плагина compose. Запустите Docker Desktop/daemon и повторите."
    exit 1
fi

if [ -z "$PYTHON" ]; then
    echo "Для локального запуска нужен Python 3.11+."
    exit 1
fi

echo
echo "== Локальный запуск =="
if [ ! -d backend/.venv ]; then
    "$PYTHON" -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install -q --disable-pip-version-check -r backend/requirements.txt

echo "API:  http://localhost:8000"
echo "UI:   file://$PWD/frontend/index.html"
echo "Вход: логин и пароль, заданные при настройке."
echo
exec backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend
