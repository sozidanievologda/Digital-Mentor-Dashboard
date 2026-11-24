from typing import Optional

from fastapi import APIRouter

from ..services.data_processing import (
    get_current_metrics,
    get_history_data,
    get_tags_data,
    refresh_and_get_metrics,
)

router = APIRouter()


@router.get("/tags")
def get_tags():
    return get_tags_data()


@router.get("/metrics")
def get_metrics(tags: Optional[str] = None):
    return get_current_metrics(tags_raw=tags)


@router.get("/history")
def get_history(
    period: str = "30d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    group: str = "day",
    tags: Optional[str] = None,
):
    return get_history_data(period=period, start=start, end=end, group=group, tags_raw=tags)


@router.post("/refresh")
def refresh(tags: Optional[str] = None):
    return refresh_and_get_metrics(tags_raw=tags)
