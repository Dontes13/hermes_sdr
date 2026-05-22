import os
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.src.api.auth import _PASSWORD_HASH, create_jwt, verify_password
from agent.src.api.routes import (
    campaigns,
    chat,
    config,
    leads,
    replies,
    run,
    stats,
    test_send,
    webhooks,
)


class LoginRequest(BaseModel):
    password: str


def create_app() -> FastAPI:
    app = FastAPI(title="Helios SDR API", version="0.2.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "https://hermes-phi-tawny.vercel.app",
        ],
        allow_origin_regex=os.environ.get(
            "CORS_ORIGIN_REGEX",
            r"https://hermes.*\.vercel\.app",
        ),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
    app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(run.router, prefix="/api/run", tags=["run"])
    app.include_router(replies.router, prefix="/api/replies", tags=["replies"])
    app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(test_send.router, prefix="/api/test-send", tags=["dev"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        tb = traceback.format_exc()
        import structlog
        log = structlog.get_logger(__name__)
        log.error("unhandled_exception", path=str(request.url.path), error=str(exc), traceback=tb)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )

    @app.post("/auth/login")
    def login(body: LoginRequest):
        if not verify_password(body.password, _PASSWORD_HASH):
            raise HTTPException(401, "Invalid password")
        return {"token": create_jwt()}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
