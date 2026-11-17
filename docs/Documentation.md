Установка и запуск

Предварительные требования

- Python 3.11+ (желательно в virtualenv)
- Docker + Compose v2 (опционально)

Быстрый старт

- Linux/macOS: `./setup.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File .\setup.ps1`

Скрипт заполняет `backend/.env` (ключ, логин, хеш пароля, `SESSION_SECRET`, CORS) и запускает Docker либо локальный `uvicorn`. Повторный запуск сохраняет существующие секреты.

Запуск через Docker (рекомендовано)

1. Создайте `backend/.env` по шаблону `backend/.env.example`.
2. Укажите `MOYKLASS_API_KEY`, `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD_HASH` и `SESSION_SECRET` (см. «Конфигурация»).
3. Из корня репозитория выполните:

       docker compose up -d --build

4. Откройте `http://localhost:8080` и войдите под учётной записью дашборда.

Контейнер `frontend` (nginx) раздаёт статику и проксирует `/api/` в `backend`. База SQLite хранится в docker-томе `dashboard-data` и переживает перезапуск контейнера.

Локальный запуск

       cd backend
       python3 -m venv .venv
       source .venv/bin/activate        # Windows: .venv\Scripts\activate
       pip install -r requirements.txt
       python -m uvicorn app.main:app --reload --port 8000

Затем откройте `frontend/index.html` (file://) — клиент обратится к `http://localhost:8000`. Либо используйте Docker-запуск выше.

Конфигурация

Все настройки читаются из `backend/.env` (шаблон — `backend/.env.example`); `.env` не коммитится.

Обязательные переменные:

- `MOYKLASS_API_KEY` — ключ API «МойКласс».
- `DASHBOARD_USERNAME` — логин дашборда.
- `DASHBOARD_PASSWORD_HASH` — PBKDF2-хеш пароля. Сгенерировать:

      cd backend
      python scripts/hash_password.py

- `SESSION_SECRET` — длинная случайная строка для подписи токенов.

Основные необязательные переменные:

- `SESSION_TTL_SECONDS` — время жизни токена (по умолчанию 43200 = 12 часов).
- `DATABASE_PATH` — путь к SQLite (по умолчанию `backend/data/dashboard.db`).
- `REFRESH_INTERVAL_SECONDS` — период фонового обновления (3600).
- `DATA_TTL_SECONDS` — после какого возраста данные считаются устаревшими (3600).
- `PROJECT_TAG_PREFIX` — префикс тегов участников проекта (по умолчанию `ФПГ_ЦН`).
- `PROJECT_TAG_NAMES` — точный список тегов через запятую (альтернатива префиксу).
- `PROJECT_START_DATE` — начало проекта для оценочного бэкфилла истории (2025-02-01).
- `CORS_ORIGINS` — список origin, которым разрешены запросы к API (по умолчанию локальные адреса и `null` для file://). В продакшене укажите только домен дашборда.
- `MOYKLASS_AUTH_URL`, `MOYKLASS_USERS_URL`, `MOYKLASS_MANAGERS_URL` — адреса API.

Структура бэкенда

- `app/main.py` — FastAPI, lifespan (инициализация БД, первичная загрузка, планировщик).
- `app/api/auth.py` — вход, проверка сессии, выход.
- `app/api/dashboard_data.py` — метрики, история, принудительное обновление.
- `app/security.py` — хеширование пароля, подписанные Bearer-токены, rate limit входа.
- `app/services/crm_service.py` — клиент API «МойКласс»: токен, пагинация, ретраи.
- `app/services/collector.py` — фильтр участников проекта, обновление, снапшоты, планировщик.
- `app/services/storage.py` — SQLite: пользователи, теги, волонтёры, снапшоты, метаданные.
- `app/services/data_processing.py` — метрики и временные ряды из снапшотов.

Аутентификация

- Один аккаунт аналитика из `DASHBOARD_USERNAME` + `DASHBOARD_PASSWORD_HASH` (или `DASHBOARD_PASSWORD` только для разработки).
- `POST /api/auth/login` возвращает подписанный Bearer-токен; фронтенд хранит его в `localStorage` и передаёт в заголовке `Authorization`.
- Все роуты `/api/dashboard/*` требуют токен; без него — 401.
- Не более 10 неудачных попыток входа за 5 минут с одного IP (429).
- Токены stateless: при выходе клиент удаляет токен, на сервере хранить сессии не нужно.

Интеграция с CRM «МойКласс»

- `get_token_api()` кэширует `accessToken` до `expiresAt` (~7 дней); при 401 токен сбрасывается и запрашивается заново.
- Страницы по 500 записей (максимум API; больше — `RequestValidationError`), число страниц берётся из `stats.totalItems`, загрузка параллельная (4 воркера).
- Записи дедуплицируются по `id`. Если страница не приносит новых записей (эндпоинт `/managers` игнорирует `offset`), загрузка останавливается.
- Ретраи: до 3 попыток с экспоненциальным backoff и учётом `Retry-After` для 429/5xx и сетевых ошибок.
- Секреты и ключи не попадают в браузер: фронтенд обращается только к собственному бэкенду.

Фильтрация участников проекта

- Участник — пользователь, у которого есть тег с префиксом `ФПГ_ЦН` (или тег из `PROJECT_TAG_NAMES`).
- API «МойКласс» не поддерживает серверную фильтрацию по тегам (параметры `tags`/`tagIds` игнорируются), поэтому фильтрация выполняется на бэкенде после выгрузки.
- Количество участников считается по уникальным `user.id` (пересечения тегов не задваивают счётчик). На момент внедрения — 736 участников из 3519 пользователей CRM.

Хранение и планировщик

- SQLite (WAL) хранит: `users` (с флагом `is_project`), `tags`, `user_tags`, `managers`, `snapshots`, `meta`.
- При каждом обновлении данные перезаписываются, а в `snapshots` пишется срез на текущую дату: участники проекта, всего пользователей, волонтёры.
- Планировщик запускает обновление раз в `REFRESH_INTERVAL_SECONDS` (час). Дополнительно обновление запускается по запросу, если данные старше `DATA_TTL_SECONDS`, и по кнопке «Обновить».
- Обновления защищены блокировкой: одновременно выполняется только одно.
- Запускайте один процесс uvicorn (без `--workers`): планировщик и SQLite рассчитаны на один инстанс.

История

- График строится из таблицы `snapshots`, а не из `createdAt`/`lastLogin` пользователей.
- При первом запуске выполняется оценочный бэкфилл: кумулятивное число пользователей по датам создания карточек, начиная с `PROJECT_START_DATE`. Такие точки помечаются `source='backfill'`, а API возвращает `approximate: true`.
- После первого сбора реальные снапшоты заменяют оценку за соответствующие дни.
- Параметры: `7d`, `30d`, `90d`, `quarter`, `all` или произвольный интервал `start`/`end` (до 730 дней).

API эндпоинты

Публичные:

- `GET /` — приветствие.
- `GET /api/health` — статус сервиса и данных.
- `POST /api/auth/login` — `{username, password}` → `{access_token, token_type, expires_in}`.

Требуют `Authorization: Bearer <token>`:

- `GET /api/auth/me` — текущий пользователь.
- `POST /api/auth/logout` — подтверждение выхода.
- `GET /api/dashboard/metrics` — ключевые метрики.
- `GET /api/dashboard/history?period=30d` — временные ряды.
- `GET /api/dashboard/history?start=2026-01-01&end=2026-01-31` — произвольный интервал.
- `POST /api/dashboard/refresh` — принудительное обновление из CRM.

Пример метрик:

      {
        "pensioners_count": 736,
        "volunteers_count": 198,
        "total_users": 3519,
        "last_updated": "2026-11-17T14:55:00",
        "last_success_at": "2026-11-17T14:55:00",
        "status": "active",
        "data_status": "live",
        "error": null
      }

`data_status`: `live` — данные свежие, `stale` — показан последний снимок, CRM недоступна или данные старше TTL, `error` — успешных загрузок ещё не было (тогда `/metrics` вернёт 503).

Пример истории:

      {
        "period": "30d",
        "start": "2026-10-19",
        "end": "2026-11-17",
        "source": "snapshots",
        "approximate": true,
        "pensioners": [{"date": "2026-10-19", "count": 735}, ...],
        "volunteers": [{"date": "2026-10-19", "count": 198}, ...]
      }

Фронтенд

- `frontend/js/api_client.js` — axios-клиент, Bearer-токен, базовый URL (same-origin в Docker, `localhost:8000` для file://).
- `frontend/js/main.js` — вход, метрики, график Chart.js, периоды (7/30/90 дней, квартал, всё время) и произвольный интервал, экспорт CSV, статус подключения, автообновление раз в 5 минут.
- `frontend/css/style.css` — адаптивная вёрстка (ПК и планшет).

Эксплуатация

- Логи: `docker compose logs -f backend`.
- Бэкап БД: том `dashboard-data` (или `backend/data/dashboard.db` при локальном запуске).
- Сброс данных: `docker compose down -v` (удалит том) либо удалить файл БД.
- Healthcheck контейнера бэкенда: `GET /` внутри контейнера.
- Прод-развёртывание, HTTPS, бэкапы и ротация секретов: `docs/DEPLOYMENT.md`.
- Сверка с CRM для приёмки: `cd backend && python scripts/verify_metrics.py --details` (`docs/ACCEPTANCE.md`).
