"""Точка входа FastAPI."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import admin, auth, student
from app.core.config import settings
from app.db import SessionLocal, run_migrations
from app.deps import csrf_protect
from app.seed import ensure_admin, seed_demo
from app.services import diploma_pdf

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    for sub in ("photos", "diplomas", "imports"):
        (Path(settings.data_dir) / sub).mkdir(parents=True, exist_ok=True)
    run_migrations()
    with SessionLocal() as db:
        ensure_admin(db)
        diploma_pdf.ensure_default_template(db)
        if settings.seed_on_start:
            seed_demo(db)
    yield


app = FastAPI(title="Школьные конкурсы", docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None, lifespan=lifespan, dependencies=[Depends(csrf_protect)])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    logging.getLogger("app").exception("Необработанная ошибка: %s", exc)
    return JSONResponse({"detail": "Внутренняя ошибка сервера"}, status_code=500)


app.include_router(auth.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def public_config():
    """Публичные настройки для фронтенда."""
    return {"require_consent": settings.require_consent, "school_name": settings.school_name}
