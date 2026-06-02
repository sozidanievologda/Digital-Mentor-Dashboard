import requests
from ..utils.config import API_KEY, URL_AUTH, USERS_API_URL, MANAGERS_API_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_token_api():
    post_auth = {'apiKey': API_KEY}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(URL_AUTH, json=post_auth, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()['accessToken']
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка аутентификации: {e}")
        raise Exception(f"Ошибка аутентификации: {e}")

def _extract_items_from_response(data, possible_keys):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in possible_keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
        for value in data.values():
            if isinstance(value, list):
                return value
    return []


def fetch_all_users():
    try:
        access_token = get_token_api()
        limit = 100
        offset = 0
        all_users = []
        page = 0
        max_pages = 50

        while True:
            page += 1
            params = {'limit': limit, 'offset': offset}
            headers = {"x-access-token": access_token, "Content-Type": "application/json"}

            try:
                response = requests.get(USERS_API_URL, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                users = _extract_items_from_response(data, ['users', 'data', 'items'])

                logger.info(f"Страница {page}: получено {len(users)} пенсионеров")
                if not users:
                    break

                all_users.extend(users)
                if len(users) < limit:
                    break

                if page >= max_pages:
                    logger.warning(f"Достигнут максимум страниц ({max_pages}) для пользователей; останавливаю разбивку.")
                    break

                offset += limit
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при получении пользователей: {e}")
                raise Exception(f"Ошибка при получении пользователей: {e}")

        logger.info(f"Получено {len(all_users)} пенсионеров")
        enabled_count = sum(1 for u in all_users if u.get('enabled'))
        disabled_count = sum(1 for u in all_users if not u.get('enabled'))
        logger.info(f"Активных: {enabled_count}, Неактивных: {disabled_count}")
        return all_users
    except Exception as e:
        logger.error(f"Ошибка в fetch_all_users: {e}")
        raise e


def fetch_all_managers():
    try:
        access_token = get_token_api()
        limit = 100
        offset = 0
        all_managers = []
        page = 0
        max_pages = 50

        while True:
            page += 1
            params = {'limit': limit, 'offset': offset}
            headers = {"x-access-token": access_token, "Content-Type": "application/json"}

            try:
                response = requests.get(MANAGERS_API_URL, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                managers = _extract_items_from_response(data, ['managers', 'data', 'items'])

                logger.info(f"Страница {page}: получено {len(managers)} волонтеров")
                if not managers:
                    break

                all_managers.extend(managers)
                if len(managers) < limit:
                    break

                if page >= max_pages:
                    logger.warning(f"Достигнут максимум страниц ({max_pages}) для волонтеров; останавливаю разбивку.")
                    break

                offset += limit
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при получении менеджеров: {e}")
                raise Exception(f"Ошибка при получении менеджеров: {e}")

        logger.info(f"Получено {len(all_managers)} волонтеров")
        
        # Debug: log first manager's keys
        if all_managers:
            logger.info(f"Поля первого волонтёра: {list(all_managers[0].keys())}")
        
        enabled_count = sum(1 for m in all_managers if m.get('enabled'))
        disabled_count = sum(1 for m in all_managers if not m.get('enabled'))
        logger.info(f"Волонтёры - Активных: {enabled_count}, Неактивных: {disabled_count}")
        
        return all_managers
    except Exception as e:
        logger.error(f"Ошибка в fetch_all_managers: {e}")
        raise e
