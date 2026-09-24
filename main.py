"""ALMIGHTY AI — application entrypoint (FastAPI)."""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import init_db, log as audit_log
from .routes_admin import router as admin_router
from .routes_auth import router as auth_router
from .routes_generate import router as gen_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("almighty")


def create_app() -> FastAPI:
    config.ensure_dirs()
    admin_password = init_db()
    if admin_password:
        logger.info("=" * 64)
        logger.info("OWNER ACCOUNT CREATED")
        logger.info("  email:    %s", config.ADMIN_EMAIL)
        logger.info("  password: %s   (also saved server-side in data/initial_admin_password.txt)",
                    admin_password)
        logger.info("  Change it after first login. Never ship this in frontend code.")
        logger.info("=" * 64)

    app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION,
                  docs_url="/api/docs", openapi_url="/api/openapi.json")

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(gen_router, prefix="/api", tags=["generation"])
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}

    @app.exception_handler(Exception)
    async def unhandled(request, exc):  # noqa: ANN001
        audit_log("error", "unhandled-exception", str(request.url.path), repr(exc)[:500])
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    static_dir = Path(__file__).resolve().parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/{path:path}")
    def spa(path: str):  # single-page frontend
        return FileResponse(static_dir / "index.html")

    return app


app = create_app()
