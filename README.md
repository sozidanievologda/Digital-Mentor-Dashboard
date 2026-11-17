Digital Mentor Dashboard — веб-приложение для визуализации данных о пенсионерах и волонтерах из CRM "МойКласс".

## Описание

Digital Mentor Dashboard — это веб-приложение, которое получает данные о пенсионерах и волонтерах из CRM "МойКласс" и визуализирует их на интерактивной панели управления. Проект состоит из бэкенда на FastAPI и фронтенда на HTML/CSS/JavaScript.

## Структура проекта

digital_mentor_dashboard/

│

├── backend/

│   ├── app/

│   │   ├── main.py                # Основной файл FastAPI

│   │   ├── api/

│   │   │   └── dashboard_data.py  # API эндпоинты

│   │   ├── services/

│   │   │   ├── crm_service.py     # Функции для работы с API

│   │   │   └── data_processing.py # Обработка данных

│   │   └── utils/

│   │       └── config_utils.py    # Конфигурация

│   ├── requirements.txt           # Зависимости Python

│   └── Dockerfile                 # Docker конфигурация

│

├── frontend/

│   ├── index.html                 # HTML страница

│   ├── css/

│   │   └── style.css              # Стили

│   └── js/

│       ├── main.js                # Основной JavaScript

│       └── api_client.js          # Клиент для работы с API

│

└── README.md                      # Документация

## Конфигурация

API-ключ CRM «МойКласс» не хранится в репозитории и передаётся через переменные окружения:

1. Скопируйте `backend/.env.example` в `backend/.env`.
2. Укажите ключ в `MOYKLASS_API_KEY`.
3. Остальные переменные (`MOYKLASS_AUTH_URL`, `MOYKLASS_USERS_URL`, `MOYKLASS_MANAGERS_URL`) опциональны — по умолчанию используются публичные адреса API.

Файл `backend/.env` добавлен в `.gitignore` и не должен попадать в git. В Docker переменные окружения передаются через `--env-file` или `environment`.



