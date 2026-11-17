import logging
import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from ..utils.config import API_KEY, URL_AUTH, USERS_API_URL, MANAGERS_API_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The CRM rejects limit > 500, so 500 is the largest page we can request.
PAGE_LIMIT = 500
MAX_PAGES = 100
MAX_WORKERS = 4
TOKEN_REFRESH_MARGIN = 60  # seconds

_token_lock = threading.Lock()
_token_cache = {"value": None, "expires_at": 0.0}


def _parse_expiry(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def get_token_api():
    """Return a cached access token, refreshing it shortly before expiry."""
    with _token_lock:
        now = time.time()
        if _token_cache["value"] and now < _token_cache["expires_at"] - TOKEN_REFRESH_MARGIN:
            return _token_cache["value"]

        post_auth = {'apiKey': API_KEY}
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(URL_AUTH, json=post_auth, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка аутентификации: {e}")
            raise Exception(f"Ошибка аутентификации: {e}")

        token = payload.get("accessToken")
        if not token:
            raise Exception(f"Ошибка аутентификации: пустой ответ {payload}")

        _token_cache["value"] = token
        _token_cache["expires_at"] = _parse_expiry(payload.get("expiresAt")) or now + 3600
        return token


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


def _total_items(data):
    """Read totalItems from the CRM response metadata, if present."""
    if isinstance(data, dict):
        stats = data.get("stats")
        if isinstance(stats, dict):
            total = stats.get("totalItems")
            if isinstance(total, int) and total >= 0:
                return total
    return None


def invalidate_token():
    with _token_lock:
        _token_cache["value"] = None
        _token_cache["expires_at"] = 0.0


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            return min(30.0, float(retry_after))
        except ValueError:
            pass
    return min(8.0, 0.5 * (2 ** attempt)) + random.uniform(0, 0.3)


def _request_page(api_url, token, offset):
    params = {'limit': PAGE_LIMIT, 'offset': offset}
    headers = {"x-access-token": token, "Content-Type": "application/json"}
    attempts = 3

    for attempt in range(attempts):
        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException as exc:
            if attempt == attempts - 1:
                raise Exception(str(exc))
            time.sleep(_retry_delay(None, attempt))
            continue

        if response.status_code == 401:
            invalidate_token()
            token = get_token_api()
            headers["x-access-token"] = token
            if attempt == attempts - 1:
                response.raise_for_status()
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == attempts - 1:
                response.raise_for_status()
            time.sleep(_retry_delay(response, attempt))
            continue

        response.raise_for_status()
        return response.json()

    raise Exception("Не удалось получить страницу данных из CRM")


def _dedupe(pages):
    """Flatten pages in order, dropping records with an already seen id."""
    all_items = []
    seen_ids = set()
    for _, items in pages:
        for item in items:
            item_id = item.get("id")
            if item_id is not None:
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
            all_items.append(item)
    return all_items


def _fetch_all_pages(api_url, possible_keys, entity_label):
    """Load every record, in parallel when the API reports a total count.

    Some MoyKlass endpoints ignore limit/offset and return the same list on
    every page, so records are deduplicated by id and pagination stops as
    soon as a page brings nothing new.
    """
    token = get_token_api()

    first_data = _request_page(api_url, token, 0)
    first_items = _extract_items_from_response(first_data, possible_keys)
    if not first_items:
        return []

    total = _total_items(first_data)
    pages = [(0, first_items)]

    if total is not None:
        total_pages = max(1, math.ceil(total / PAGE_LIMIT))
        if total_pages > MAX_PAGES:
            logger.warning(
                f"Для {entity_label} требуется {total_pages} страниц, "
                f"но лимит {MAX_PAGES}; данные могут быть неполными"
            )
            total_pages = MAX_PAGES

        if total_pages > 1:
            offsets = [page * PAGE_LIMIT for page in range(1, total_pages)]

            def fetch_page(offset):
                data = _request_page(api_url, token, offset)
                return offset, _extract_items_from_response(data, possible_keys)

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                pages.extend(
                    sorted(
                        executor.map(fetch_page, offsets),
                        key=lambda pair: pair[0],
                    )
                )
    else:
        # No total in the response: walk pages until a short or repeated one.
        offset = len(first_items)
        page = 1
        while len(first_items) >= PAGE_LIMIT and page < MAX_PAGES:
            page += 1
            data = _request_page(api_url, token, offset)
            items = _extract_items_from_response(data, possible_keys)
            if not items:
                break

            seen_ids = {item.get("id") for item in first_items if item.get("id") is not None}
            new_items = [
                item for item in items
                if item.get("id") is None or item.get("id") not in seen_ids
            ]
            if not new_items:
                logger.warning(
                    f"{entity_label.capitalize()}: страница {page} не содержит новых записей — "
                    f"API игнорирует пагинацию, останавливаю загрузку"
                )
                break

            pages.append((offset, items))
            first_items = items
            offset += len(items)

    all_items = _dedupe(pages)
    logger.info(
        f"{entity_label.capitalize()}: загружено страниц {len(pages)}, "
        f"записей {len(all_items)} (totalItems={total})"
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

        enabled_count = sum(1 for m in all_managers if m.get('enabled'))
        disabled_count = sum(1 for m in all_managers if not m.get('enabled'))
        logger.info(f"Волонтёры - Активных: {enabled_count}, Неактивных: {disabled_count}")

        return all_managers
    except Exception as e:
        logger.error(f"Ошибка в fetch_all_managers: {e}")
        raise e
