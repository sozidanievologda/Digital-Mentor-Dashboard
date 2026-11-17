import requests
from ..utils.config import API_KEY, URL_AUTH, USERS_API_URL, MANAGERS_API_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PAGE_LIMIT = 100
MAX_PAGES = 50


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


def _fetch_all_pages(api_url, possible_keys, entity_label):
    """Загружает все записи, защищаясь от API без рабочей пагинации.

    Некоторые эндпоинты «МойКласс» игнорируют limit/offset и возвращают
    один и тот же список на любой странице. Чтобы не превращать это в
    дубликаты, останавливаемся, когда страница не приносит новых записей
    (сравнение по id).
    """
    access_token = get_token_api()
    offset = 0
    all_items = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        params = {'limit': PAGE_LIMIT, 'offset': offset}
        headers = {"x-access-token": access_token, "Content-Type": "application/json"}

        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении {entity_label}: {e}")
            raise Exception(f"Ошибка при получении {entity_label}: {e}")

        items = _extract_items_from_response(data, possible_keys)
        if not items:
            break

        new_items = []
        for item in items:
            item_id = item.get("id")
            if item_id is not None:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            new_items.append(item)

        if not new_items:
            logger.warning(
                f"{entity_label.capitalize()}: страница {page} не содержит новых записей — "
                f"API игнорирует пагинацию, останавливаю загрузку"
            )
            break

        all_items.extend(new_items)
        logger.info(
            f"Страница {page}: получено {len(items)} {entity_label}, "
            f"новых: {len(new_items)}, всего: {len(all_items)}"
        )

        if len(items) < PAGE_LIMIT:
            break

        if len(new_items) < len(items):
            logger.warning(
                f"{entity_label.capitalize()}: страница {page} содержит уже загруженные "
                f"записи — пагинация не продвигается, останавливаю загрузку"
            )
            break

        offset += len(items)
    else:
        logger.warning(
            f"Достигнут максимум страниц ({MAX_PAGES}) для {entity_label}: "
            f"загружено {len(all_items)} записей, данные могут быть неполными"
        )

    return all_items


def fetch_all_users():
    try:
        all_users = _fetch_all_pages(USERS_API_URL, ['users', 'data', 'items'], "пользователей")
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
        all_managers = _fetch_all_pages(MANAGERS_API_URL, ['managers', 'data', 'items'], "волонтёров")
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
