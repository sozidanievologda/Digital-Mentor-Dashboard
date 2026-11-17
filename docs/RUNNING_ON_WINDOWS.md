# Запуск на Windows

Проект можно запустить двумя способами: через Docker Desktop (рекомендуется) или локально на Python. Инструкции ниже — для PowerShell; в CMD команды те же, кроме активации venv.

## Что понадобится

| Вариант | Требования |
|---|---|
| Docker | Windows 10/11 x64, Docker Desktop 4.x с WSL 2, Git |
| Без Docker | Python 3.11+ (лучше 3.12), Git |

Ключ CRM «МойКласс» (`MOYKLASS_API_KEY`) должен быть у вас на руках.

---

## Вариант 1. Docker Desktop (рекомендуется)

Поднимаются два контейнера: бэкенд FastAPI и nginx, который раздаёт фронтенд и проксирует `/api`. Наружу открыт только порт **8080**.

### 1. Установить Docker Desktop

Скачайте с <https://www.docker.com/products/docker-desktop/>, установите, при первом запуске оставьте включённым **WSL 2 based engine** (Windows 11) или включите WSL 2 вручную (Windows 10). Дождитесь, пока Docker Desktop перейдёт в статус **Running**.

Проверьте в новом окне PowerShell:

```powershell
docker --version
docker compose version
```

Обе команды должны отработать без ошибок. Если `docker compose` неизвестен — обновите Docker Desktop (Compose v2 входит в него).

### 2. Получить проект

```powershell
git clone <URL-репозитория> Digital-Mentor-Dashboard
cd Digital-Mentor-Dashboard
```

Если проект уже склонирован — просто перейдите в его папку.

### 3. Создать `.env` с ключом

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Вставьте ключ в строку `MOYKLASS_API_KEY=...`, сохраните файл (кодировка ASCII или UTF-8 без BOM — ключ и адреса состоят из латиницы). Файл `backend\.env` уже в `.gitignore`, коммитить его нельзя.

### 4. Запустить

```powershell
docker compose up -d --build
```

Первый запуск занимает несколько минут: скачиваются образы и ставятся зависимости.

### 5. Открыть дашборд

- Дашборд: <http://localhost:8080>
- Swagger: <http://localhost:8080/docs>

Первый запрос к метрикам может занять **30–60 секунд**: бэкенд постранично выгружает данные из CRM, дальше 5 минут работает кэш.

Если Windows покажет запрос от брандмауэра — разрешите доступ для Docker.

### 6. Полезные команды

```powershell
docker compose logs -f backend   # логи бэкенда
docker compose logs -f frontend  # логи nginx
docker compose restart backend   # перезапуск
docker compose down              # остановить
docker compose up -d --build     # пересобрать после изменений
```

---

## Вариант 2. Без Docker (Python)

### 1. Установить Python

Скачайте Python 3.12 с <https://www.python.org/downloads/windows/>. При установке обязательно отметьте **Add python.exe to PATH**.

Проверьте:

```powershell
py -3.12 --version
```

Если команда `python` открывает Microsoft Store, используйте `py -3.12` (лаунчер Python) либо отключите алиасы в «Параметры → Приложения → Псевдонимы выполнения приложений».

### 2. Создать окружение и поставить зависимости

Из корня проекта:

```powershell
py -3.12 -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Если PowerShell блокирует активацию (`running scripts is disabled on this system`), разрешите её только для текущего окна:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\backend\.venv\Scripts\Activate.ps1
```

В CMD вместо этого: `backend\.venv\Scripts\activate.bat`. В Git Bash: `source backend/.venv/Scripts/activate`.

### 3. Создать `.env`

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Впишите `MOYKLASS_API_KEY` и сохраните.

### 4. Запустить бэкенд

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Окно должно оставаться открытым. Проверка в другом окне PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/dashboard/metrics
```

(В PowerShell `curl` — это псевдоним `Invoke-WebRequest`; если удобнее классический curl, используйте `curl.exe`.)

### 5. Открыть фронтенд

В новом окне PowerShell из корня проекта:

```powershell
start frontend\index.html
```

Страница откроется по `file://`, и клиент автоматически обратится к `http://localhost:8000`. CORS на бэкенде разрешён, поэтому этот способ работает.

> Не запускайте фронтенд через `python -m http.server`: в этом режиме клиент использует относительный путь `/api`, а прокси в таком случае нет. Для HTTP-раздачи используйте Docker-вариант.

### 6. Остановить

`Ctrl+C` в окне с uvicorn. Деактивировать окружение — `deactivate`.

---

## Что должно получиться

| Режим | URL дашборда | API |
|---|---|---|
| Docker | `http://localhost:8080` | `http://localhost:8080/api/dashboard/...` (через nginx) |
| Python | `frontend\index.html` (file://) | `http://localhost:8000/api/dashboard/...` |

Метрики приходят из CRM: количество пенсионеров и волонтёров, плюс история за 7/30/90 дней или всё время.

---

## Частые проблемы

| Симптом | Решение |
|---|---|
| `docker: command not found` | Docker Desktop не установлен или не в PATH — перезапустите PowerShell после установки |
| `docker compose` — unknown command | Обновите Docker Desktop; как запасной вариант используйте `docker-compose` |
| `failed to connect to the docker API` | Docker Desktop не запущен — запустите и дождитесь статуса Running |
| `env file ... not found` | Не создан `backend\.env` — выполните `Copy-Item backend\.env.example backend\.env` |
| Порт 8080 занят | `netstat -ano \| findstr :8080`, затем `taskkill /PID <pid> /F`; либо поменяйте `"8080:80"` в `docker-compose.yml` |
| Порт 8000 занят (локальный запуск) | Запустите uvicorn на другом порту (`--port 8001`) либо закройте старый процесс |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| Метрики долго грузятся или `status: error` | CRM иногда обрывает соединение при выгрузке; повторите запрос и посмотрите `docker compose logs -f backend` |
| В дашборде нули | Проверьте ключ в `backend\.env` и логи бэкенда; при ошибке CRM API отдаёт 200 с нулями и текстом в `status` |
| Данные не обновились | Кэш бэкенда — 5 минут; перезапустите бэкенд или подождите |
| Кириллица в логах/файлах | Файлы проекта в UTF-8; для `.env` достаточно ASCII |

## Безопасность

- `backend\.env` содержит секрет: не коммитьте его и не отправляйте в чаты.
- Если ключ попал в git-историю или публичный репозиторий — перевыпустите его в кабинете «МойКласс».
