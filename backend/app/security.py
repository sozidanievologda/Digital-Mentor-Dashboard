import hmac
import logging
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .utils import config
from .utils.passwords import create_token, verify_password, verify_token

logger = logging.getLogger(__name__)

# A missing SESSION_SECRET still works, but tokens become invalid on restart.
_secret = config.SESSION_SECRET or secrets.token_hex(32)
if not config.SESSION_SECRET:
    logger.warning(
        "SESSION_SECRET is not set; dashboard sessions will be invalidated on restart"
    )

_bearer = HTTPBearer(auto_error=False)

_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_ATTEMPTS = 10
_attempts = defaultdict(deque)
_attempts_lock = threading.Lock()


def auth_configured() -> bool:
    return bool(
        config.DASHBOARD_USERNAME
        and (config.DASHBOARD_PASSWORD_HASH or config.DASHBOARD_PASSWORD)
    )


def credentials_valid(username: str, password: str) -> bool:
    if not auth_configured():
        return False

    user_ok = hmac.compare_digest(
        username.encode("utf-8"), config.DASHBOARD_USERNAME.encode("utf-8")
    )
    if not user_ok:
        return False

    if config.DASHBOARD_PASSWORD_HASH:
        return verify_password(password, config.DASHBOARD_PASSWORD_HASH)
    return hmac.compare_digest(
        password.encode("utf-8"), config.DASHBOARD_PASSWORD.encode("utf-8")
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_login_rate(request: Request):
    now = time.time()
    with _attempts_lock:
        attempts = _attempts[_client_ip(request)]
        while attempts and now - attempts[0] > _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много попыток входа, попробуйте позже",
            )


def register_login_failure(request: Request):
    with _attempts_lock:
        _attempts[_client_ip(request)].append(time.time())


def reset_login_attempts(request: Request):
    with _attempts_lock:
        _attempts.pop(_client_ip(request), None)


def create_access_token(username: str) -> str:
    return create_token(username, _secret, config.SESSION_TTL_SECONDS)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    username = verify_token(credentials.credentials, _secret)
    if not username:
        raise unauthorized
    return username
