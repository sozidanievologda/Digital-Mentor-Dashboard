# Развёртывание и администрирование

Инструкция для боевого сервера: HTTPS, обновления, бэкапы, ротация секретов и мониторинг.

## 1. Требования

- Linux-сервер (проверено на Ubuntu 22.04/24.04), 1 CPU / 1 ГБ RAM / 10 ГБ диска.
- Docker Engine и Compose v2.
- Домен, A-запись которого указывает на IP сервера.
- Открытые порты **80** и **443** (для выпуска сертификата и HTTPS).

## 2. Подготовка

```bash
sudo apt update && sudo apt install -y git
git clone <URL-репозитория> Digital-Mentor-Dashboard
cd Digital-Mentor-Dashboard

cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Заполните `backend/.env`:

```ini
MOYKLASS_API_KEY=...
DASHBOARD_USERNAME=analyst
DASHBOARD_PASSWORD_HASH=pbkdf2_sha256$...
SESSION_SECRET=<64+ случайных символа>
CORS_ORIGINS=https://dashboard.example.com
```

- Хеш пароля: `cd backend && python3 scripts/hash_password.py` (нужен Python 3.11+; можно сгенерировать локально и вставить на сервер).
- `SESSION_SECRET`: `openssl rand -hex 32`.
- `CORS_ORIGINS` — только реальный домен; запросы через nginx и так same-origin.

## 3. Запуск с HTTPS (Caddy)

В `docker-compose.prod.yml` добавлен Caddy, который автоматически получает сертификат Let's Encrypt.

```bash
export DASHBOARD_DOMAIN=dashboard.example.com
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Проверьте выпуск сертификата:

```bash
docker compose logs -f caddy
```

Наружу открыты только 80/443. Порт `8080` привязан к `127.0.0.1` и доступен только с самого сервера.

Firewall (пример для ufw):

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 4. Проверка после запуска

- `https://dashboard.example.com` — страница входа.
- `https://dashboard.example.com/api/health` — `{"status":"ok","data_status":"live",...}`.
- `docker compose ps` — контейнеры `backend`, `frontend`, `caddy` в состоянии healthy/running.
- `curl -I https://dashboard.example.com` — есть `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`.

Первая загрузка данных из CRM занимает ~15–20 секунд; до её окончания `/api/dashboard/metrics` отвечает 503.

## 5. Обновление версии

```bash
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

База в томе `dashboard-data` сохраняется. Схема SQLite создаётся автоматически (`CREATE TABLE IF NOT EXISTS`).

## 6. Бэкап и восстановление

SQLite-база: `backend/data/dashboard.db` внутри контейнера (том `dashboard-data`).

Бэкап (consistent copy через SQLite backup API):

```bash
mkdir -p backups
docker compose exec -T backend python -c "import sqlite3; s=sqlite3.connect('/app/data/dashboard.db'); d=sqlite3.connect('/app/data/backup.db'); s.backup(d); d.close()"
docker compose cp backend:/app/data/backup.db "backups/dashboard-$(date +%F).db"
docker compose exec -T backend rm -f /app/data/backup.db
```

Ежедневный cron (пример):

```cron
0 3 * * * cd /opt/Digital-Mentor-Dashboard && docker compose exec -T backend python -c "import sqlite3; s=sqlite3.connect('/app/data/dashboard.db'); d=sqlite3.connect('/app/data/backup.db'); s.backup(d); d.close()" && docker compose cp backend:/app/data/backup.db backups/dashboard-$(date +\%F).db
```

Восстановление:

```bash
docker compose stop backend
docker compose cp backups/dashboard-2026-11-17.db backend:/app/data/dashboard.db
docker compose start backend
```

Храните бэкапы вне сервера; удаляйте копии старше 14 дней.

## 7. Ротация секретов

После изменения `backend/.env` контейнер нужно **пересоздать**, `restart` не перечитывает env:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate backend
```

- **API-ключ CRM**: перевыпустить в «МойКласс» → обновить `MOYKLASS_API_KEY` → пересоздать `backend`.
- **Пароль дашборда**: сгенерировать новый хеш → обновить `DASHBOARD_PASSWORD_HASH` → пересоздать `backend`.
- **`SESSION_SECRET`**: после смены все выданные токены становятся недействительными (пользователи войдут заново).
- Если секрет попадал в git, документы или чат — считайте его скомпрометированным.

## 8. Мониторинг

- `GET /api/health` → `data_status` (`live`/`stale`/`error`) и `last_success_at`.
- Логи: `docker compose logs -f backend`, `... caddy`.
- Healthcheck контейнера бэкенда встроен в Dockerfile.
- Контролируйте свободное место и свежесть бэкапов.

Пример проверки по cron (алерт при `stale`):

```bash
curl -fsS https://dashboard.example.com/api/health | grep -q '"data_status":"live"' || echo "CRM data is stale" | mail -s "Dashboard alert" admin@example.com
```

## 9. Диагностика

| Симптом | Причина / решение |
|---|---|
| 401 на всех запросах | Нет/просрочен токен — войдите заново |
| 503 «Данные ещё не загружены» | Первичная загрузка ещё идёт или CRM недоступна; смотрите логи |
| `stale` в `/api/health` | CRM недоступна или не прошло часовое обновление; нажмите «Обновить» |
| Caddy не выпускает сертификат | DNS не указывает на сервер, закрыты 80/443 |
| Пустой график | Снапшоты ещё не накопились; история до внедрения помечается как оценка |
| `database is locked` | Запущено несколько процессов uvicorn с планировщиком; используйте один worker |

## 10. Ограничения текущей версии

- Один процесс uvicorn и SQLite: для отказоустойчивого кластера нужен PostgreSQL/Redis.
- История до первого запуска — оценка по датам создания карточек (`approximate: true`).
- Один аккаунт аналитика; управление ролями — в следующей версии по ТЗ.
- CSP не задаётся, чтобы не ломать Swagger UI; при необходимости добавьте заголовок в nginx.
