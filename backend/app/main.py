import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, dashboard_data
from app.security import get_current_user
from app.services import collector, storage
from app.utils import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    collector.startup_refresh()
    collector.start_scheduler()
    logger.info("Starting up...")
    yield
    collector.stop_scheduler()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(
    dashboard_data.router,
    prefix="/api/dashboard",
    dependencies=[Depends(get_current_user)],
)


@app.get("/")
def root():
    return {"message": "Welcome to Digital Mentor Dashboard API"}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_status": collector.get_data_status(),
        "last_success_at": storage.get_meta("last_success_at"),
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal server error: {str(exc)}"},
    )
