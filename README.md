# Digital Mentor Dashboard

Дашборд проекта «Цифровой наставник» (ВРОО «Созидание»): показывает количество пенсионеров, охваченных проектом, и динамику вовлечения. Данные поступают из CRM «МойКласс» через REST API, кэшируются в SQLite и обновляются в фоне раз в час.

## Возможности

- Ключевая метрика — уникальные участники проекта (пользователи CRM с тегами `ФПГ_ЦН`), а не все пользователи.
- Выбор тегов проекта: можно считать метрику и график по всем тегам, по одному или по любой комбинации.
- График динамики: накопительная линия и столбцы «сколько человек пришло за месяц» (1/3/6/12 месяцев); в режиме линии — 7/30/90 дней, квартал, 12 месяцев, всё время и произвольный интервал.
- Экспорт истории в CSV.
- Вход по логину и паролю, защита API Bearer-токеном.
- Фоновое обновление, ежедневные снапшоты, статусы `live` / `stale` / `error`.
- Docker-развёртывание: FastAPI-бэкенд + nginx с проксированием `/api`.

## Стек

- **Бэкенд:** Python 3.11+, FastAPI, uvicorn, requests, SQLite.
- **Фронтенд:** HTML/CSS/JS, Chart.js, Axios.
- **Инфраструктура:** Docker, Docker Compose, nginx.

## Структура

```
backend/
  app/
    main.py                  # FastAPI, lifespan, планировщик
    security.py              # пароли, токены, rate limit
    api/auth.py              # вход / сессия / выход
    api/dashboard_data.py    # метрики, история, обновление
    services/
      crm_service.py         # клиент «МойКласс»: токен, пагинация, ретраи
      collector.py           # участники проекта, снапшоты, планировщик
      storage.py             # SQLite
      data_processing.py     # метрики и временные ряды
    utils/
      config.py              # переменные окружения
      passwords.py           # хеширование и подпись токенов
  scripts/hash_password.py   # генератор DASHBOARD_PASSWORD_HASH
  tests/                     # pytest
frontend/
  index.html
  css/style.css
  js/api_client.js
  js/main.js
docs/
  API_SPECIFICATION.md
  Documentation.md
  RUNNING_ON_WINDOWS.md
  TZ_RESEARCH_AND_PLAN.md
docker-compose.yml
docker-compose.prod.yml
nginx.conf
setup.sh
setup.ps1
```

## Быстрый старт

**Linux / macOS:**

```bash
chmod +x setup.sh
./setup.sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Скрипт спросит API-ключ «МойКласс», логин и пароль, сгенерирует хеш пароля и `SESSION_SECRET`, заполнит `backend/.env` и запустит проект: Docker, если он доступен, иначе локальный `uvicorn`. Повторный запуск безопасен — существующие значения сохраняются.

Флаги: `--no-start` (только настроить), `--local` (без Docker), `--docker` (только Docker). Для автоматизации: переменные `DM_API_KEY`, `DM_USERNAME`, `DM_PASSWORD` и `--no-input`.

API-ключ вставляется через `Ctrl+V` (в Windows Terminal — правый клик). Если терминал не принимает вставку, скопируйте ключ в буфер обмена и нажмите Enter — скрипт возьмёт его оттуда.

## Конфигурация

Все секреты хранятся в `backend/.env` (шаблон — `backend/.env.example`), файл добавлен в `.gitignore`.

1. Скопируйте `backend/.env.example` в `backend/.env`.
2. Заполните обязательные переменные:
   - `MOYKLASS_API_KEY` — ключ API «МойКласс»;
   - `DASHBOARD_USERNAME` — логин для входа в дашборд;
   - `SESSION_SECRET` — длинная случайная строка для подписи токенов.
3. Сгенерируйте хеш пароля и вставьте его в `DASHBOARD_PASSWORD_HASH`:

   ```bash
   cd backend
   python scripts/hash_password.py
   ```

Дополнительно: `DATABASE_PATH`, `REFRESH_INTERVAL_SECONDS`, `DATA_TTL_SECONDS`, `PROJECT_TAG_PREFIX`, `PROJECT_TAG_NAMES`, `PROJECT_START_DATE` — описаны в `docs/Documentation.md`.

API дашборда защищён: без входа `/api/dashboard/*` возвращает 401. Логин и пароль — те, что заданы в `.env`.

Если вход не проходит, проверьте учётные данные и запущенный API:

```bash
cd backend
python scripts/check_auth.py --api-url http://localhost:8080/api
```

## Запуск через Docker

Требуется Docker с плагином Compose v2.

```bash
cp backend/.env.example backend/.env
# заполнить MOYKLASS_API_KEY, DASHBOARD_USERNAME, DASHBOARD_PASSWORD_HASH, SESSION_SECRET

docker compose up -d --build
```

Дашборд: `http://localhost:8080`. Swagger: `http://localhost:8080/docs` (для запросов нужен Bearer-токен из `/api/auth/login`).

Поднимаются два контейнера:

- `backend` — FastAPI/uvicorn на порту 8000, доступен только внутри docker-сети; ключ передаётся через `env_file` (`backend/.env`), в образ не копируется.
- `frontend` — nginx на порту 8080: раздаёт статику из `frontend/` и проксирует `/api/`, `/docs`, `/redoc`, `/openapi.json` в бэкенд.

База SQLite лежит в томе `dashboard-data` и переживает перезапуски. Полный сброс вместе с историей: `docker compose down -v`.

Полезные команды:

```bash
docker compose logs -f backend   # логи бэкенда
docker compose down              # остановить
docker compose up -d --build     # пересобрать после изменений
```

## Локальный запуск без Docker

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Затем откройте `frontend/index.html` в браузере: при `file://` фронтенд обращается к `http://localhost:8000`. Войдите под учётной записью из `.env`.

## Документация

- [`docs/Documentation.md`](docs/Documentation.md) — архитектура, конфигурация, эксплуатация.- [`docs/API_SPECIFICATION.md`](docs/API_SPECIFICATION.md) — описание API (Приложение Б к ТЗ).
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — развёртывание на сервере, HTTPS, бэкапы, ротация секретов.
- [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) — методика расчёта и чек-лист приёмки.
- [`docs/RUNNING_ON_WINDOWS.md`](docs/RUNNING_ON_WINDOWS.md) — запуск на Windows.
- [`docs/TZ_RESEARCH_AND_PLAN.md`](docs/TZ_RESEARCH_AND_PLAN.md) — ресерч ТЗ и план улучшений.

## Безопасность

- `backend/.env` содержит секреты и не коммитится.
- Прямых запросов к CRM из браузера нет: фронтенд работает только с собственным бэкендом.
- Если ключ или пароль попадали в git-историю или документы — перевыпустите их в CRM.
