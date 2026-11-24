from typing import Optional

from fastapi import APIRouter

from ..services.data_processing import (
    get_current_metrics,
    get_history_data,
    refresh_and_get_metrics,
)

router = APIRouter()


@router.get("/metrics")
def get_metrics():
    return get_current_metrics()


@router.get("/history")
def get_history(
    period: str = "30d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    group: str = "day",
):
    return get_history_data(period=period, start=start, end=end, group=group)


@router.post("/refresh")
def refresh():
    return refresh_and_get_metrics()
