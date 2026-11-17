Документация API

Базовый URL: `http://localhost:8000/api` (локально) или `http://localhost:8080/api` (Docker, через nginx).

Аутентификация

Все методы `/api/dashboard/*` требуют заголовок:

    Authorization: Bearer <access_token>

POST /api/auth/login

Описание: вход в дашборд.

Тело:

    {"username": "analyst", "password": "..."}

Ответ 200:

    {
      "access_token": "...",
      "token_type": "bearer",
      "expires_in": 43200
    }

Ошибки: 401 — неверный логин/пароль; 429 — слишком много попыток; 503 — авторизация не настроена на сервере.

GET /api/auth/me

Ответ 200:

    {"username": "analyst"}

POST /api/auth/logout

Ответ 200: `{"status": "ok", "username": "analyst"}`. Токен stateless — клиент удаляет его сам.

GET /api/health

Публичный статус сервиса:

    {
      "status": "ok",
      "data_status": "live",
      "last_success_at": "2026-11-17T14:55:00"
    }

GET /api/dashboard/metrics

Ответ 200:

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

Поля:

- `pensioners_count` — уникальные участники проекта (пользователи с тегами `ФПГ_ЦН`).
- `total_users` — всего пользователей в CRM (для сверки).
- `volunteers_count` — волонтёры (`/managers`).
- `data_status` — `live` | `stale` | `error`.
- `status` — `active` или `stale` (совместимость со старым фронтендом).
- `error` — последняя ошибка синхронизации, если была.

Ошибки: 401 без токена; 503, если данных ещё нет.

GET /api/dashboard/history

Параметры:

- `period` — `7d`, `30d`, `90d`, `quarter`, `all` (по умолчанию `30d`).
- `start`, `end` — произвольный интервал в формате `YYYY-MM-DD` (оба параметра обязательны, до 730 дней). При их наличии `period` игнорируется.

Ответ 200:

    {
      "period": "30d",
      "start": "2026-10-19",
      "end": "2026-11-17",
      "source": "snapshots",
      "approximate": true,
      "pensioners": [{"date": "2026-10-19", "count": 735}],
      "volunteers": [{"date": "2026-10-19", "count": 198}]
    }

- `approximate: true` — в диапазон попали оценочные точки бэкфилла (до первого реального сбора данных).
- Пропущенные дни заполняются последним известным значением.
- До первой точки значение может быть `null`.

Ошибки: 400 — неверный период или интервал; 401 — нет токена.

POST /api/dashboard/refresh

Принудительно выгружает данные из CRM и возвращает свежие метрики (может занять несколько секунд).

Ответ 200 — как у `/metrics`. Если CRM недоступна, но есть последний снимок, возвращается `data_status: "stale"` и текст ошибки в `error`.

Обработка ошибок

- Ошибки аутентификации: 401, заголовок `WWW-Authenticate: Bearer`.
- Ошибки периода: 400 с пояснением.
- Нет данных: 503.
- Ошибки CRM не «маскируются» нулями: последний успешный снимок отдаётся со статусом `stale`.
