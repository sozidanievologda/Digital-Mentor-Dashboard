# Запуск на Windows

Проект можно запустить двумя способами: через Docker Desktop (рекомендуется) или локально на Python. Инструкции ниже — для PowerShell; в CMD команды те же, кроме активации venv.

## Что понадобится

| Вариант | Требования |
|---|---|
| Docker | Windows 10/11 x64, Docker Desktop 4.x с WSL 2, Git |
| Без Docker | Python 3.11+ (лучше 3.12), Git |

Ключ CRM «МойКласс» (`MOYKLASS_API_KEY`) должен быть у вас на руках.

## Быстрый старт (рекомендуется)

Из корня проекта:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

Скрипт сам:

- найдёт Python 3.11+ (или использует Docker, если Python нет);
- спросит API-ключ, логин и пароль;
- сгенерирует `DASHBOARD_PASSWORD_HASH` и `SESSION_SECRET`;
- заполнит `backend\.env`;
- запустит Docker, если Docker Desktop работает, иначе — локальный `uvicorn`;
- откроет дашборд в браузере.

Повторный запуск безопасен: существующие ключ и хеш пароля сохраняются. Флаги: `-NoStart`, `-Local`, `-Docker`.

Ниже — те же шаги вручную.

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

### 3. Создать `.env` с ключом и учётными данными

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

Заполните:

- `MOYKLASS_API_KEY` — ключ API «МойКласс»;
- `DASHBOARD_USERNAME` — логин для входа в дашборд;
- `SESSION_SECRET` — любая длинная случайная строка (например, 64 символа);
- `DASHBOARD_PASSWORD_HASH` — хеш пароля. Сгенерировать можно так:

  ```powershell
  cd backend
  py -3.12 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python scripts\hash_password.py
  ```

  Скопируйте вывод в `DASHBOARD_PASSWORD_HASH` и вернитесь в корень: `cd ..`.

  Если Python нет, для локального запуска можно временно использовать `DASHBOARD_PASSWORD=ваш-пароль` (без хеша), но для постоянной работы лучше хеш.

Сохраните файл в ASCII или UTF-8 без BOM. Файл `backend\.env` уже в `.gitignore`, коммитить его нельзя.

### 4. Запустить

```powershell
docker compose up -d --build
```

Первый запуск занимает несколько минут: скачиваются образы и ставятся зависимости.

### 5. Открыть дашборд

- Дашборд: <http://localhost:8080>
- Swagger: <http://localhost:8080/docs>

Войдите под логином и паролем, которые указали в `backend\.env`. API без входа возвращает 401.

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

Заполните `MOYKLASS_API_KEY`, `DASHBOARD_USERNAME`, `SESSION_SECRET` и `DASHBOARD_PASSWORD_HASH` (или `DASHBOARD_PASSWORD`). Хеш пароля генерируется командой:

```powershell
python scripts\hash_password.py
```

(выполнять из папки `backend` с активированным venv).

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

Страница откроется по `file://`, и клиент автоматически обратится к `http://localhost:8000`. CORS на бэкенде разрешён, поэтому этот способ работает. Войдите под логином и паролем из `backend\.env`.

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
| `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` | Docker Desktop не запущен или Linux-движок не стартовал. Запустите Docker Desktop, дождитесь **Engine running**, проверьте `docker info` и повторите `docker compose up -d --build` |
| `env file ... not found` | Не создан `backend\.env` — выполните `Copy-Item backend\.env.example backend\.env` |
| Порт 8080 занят | `netstat -ano \| findstr :8080`, затем `taskkill /PID <pid> /F`; либо поменяйте `"8080:80"` в `docker-compose.yml` |
| Порт 8000 занят (локальный запуск) | Запустите uvicorn на другом порту (`--port 8001`) либо закройте старый процесс |
| `running scripts is disabled` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| Метрики долго грузятся или `status: error` | CRM иногда обрывает соединение при выгрузке; повторите запрос и посмотрите `docker compose logs -f backend` |
| В дашборде нули | Проверьте ключ в `backend\.env` и логи бэкенда; при ошибке CRM API отдаёт 200 с нулями и текстом в `status` |
| 401 при входе | Неверный логин/пароль или не заполнен `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD_HASH` |
| 503 «Авторизация не настроена» | В `backend\.env` не заданы учётные данные — добавьте `DASHBOARD_USERNAME` и `DASHBOARD_PASSWORD_HASH` (или `DASHBOARD_PASSWORD`) |
| Данные не обновились | Фоновое обновление раз в час; нажмите «Обновить» в дашборде или `docker compose restart backend` |
| Кириллица в логах/файлах | Файлы проекта в UTF-8; для `.env` достаточно ASCII |

### Docker Desktop не запускается или движок не поднимается

Если ошибка про `dockerDesktopLinuxEngine` повторяется даже после запуска Docker Desktop:

1. Выйдите из Docker Desktop (иконка кита в трее → **Quit Docker Desktop**) и запустите снова; дождитесь, пока в трее появится **Engine running**.
2. Проверьте, что CLI видит сервер:
   ```powershell
   docker version
   docker info
   ```
   В выводе `docker version` должен быть блок **Server**, а не только **Client**.
3. Перезапустите WSL и обновите его:
   ```powershell
   wsl --shutdown
   wsl --update
   ```
   Затем снова запустите Docker Desktop.
4. Settings → **General** → включите **Use the WSL 2 based engine** (и интеграцию с вашим дистрибутивом в **Resources → WSL Integration**).
5. Проверьте виртуализацию: Диспетчер задач → Производительность → **Виртуализация: Включена**. Если выключена — включите в BIOS/UEFI и компоненты Windows **Hyper-V** / **Virtual Machine Platform**.
6. Убедитесь, что выбран правильный контекст:
   ```powershell
   docker context ls
   docker context use desktop-linux
   ```

Если Docker так и не заводится — используйте вариант 2 (Python), он не требует Docker.

## Безопасность

- `backend\.env` содержит секрет: не коммитьте его и не отправляйте в чаты.
- Если ключ попал в git-историю или публичный репозиторий — перевыпустите его в кабинете «МойКласс».
