import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..security import (
    auth_configured,
    check_login_rate,
    create_access_token,
    credentials_valid,
    get_current_user,
    register_login_failure,
    reset_login_attempts,
)
from ..utils import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginPayload, request: Request):
    if not auth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Авторизация не настроена (DASHBOARD_USERNAME / DASHBOARD_PASSWORD_HASH)",
        )

    check_login_rate(request)

    if not credentials_valid(payload.username, payload.password):
        register_login_failure(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    reset_login_attempts(request)
    return {
        "access_token": create_access_token(payload.username),
        "token_type": "bearer",
        "expires_in": config.SESSION_TTL_SECONDS,
    }


@router.get("/me")
def me(username: str = Depends(get_current_user)):
    return {"username": username}


@router.post("/logout")
def logout(username: str = Depends(get_current_user)):
    # Tokens are stateless: the client discards the token on logout.
    return {"status": "ok", "username": username}
