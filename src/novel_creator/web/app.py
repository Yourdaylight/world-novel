"""FastAPI web application for the novel creator dashboard."""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from novel_creator.log import get_logger
from novel_creator.web.events import get_event_queue
from novel_creator.web.routes import router

logger = get_logger("novel_creator.web")

app = FastAPI(title="WorldNovel Dashboard", version="0.6.0")

# CORS — allow local dev (Vite dev server)
# 生产环境应限制为具体域名
_cors_origins = os.environ.get("NOVEL_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins != ["*"] else ["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Request-Id"],
    max_age=600,
)

app.include_router(router, prefix="/api")


# ── Health endpoint ──────────────────────────────────────
@app.get("/api/health")
async def health():
    """Quick health check for smoke tests and monitoring."""
    return {"status": "ok", "version": "0.5.0"}


# ── Security headers middleware ─────────────────────────
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """添加安全响应头部，防止常见Web攻击。"""
    response = await call_next(request)
    # 防止MIME类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"
    # 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"
    # XSS保护
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # 限制Referrer信息泄漏
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # 简单的CSP策略
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:;"
    )
    return response


# ── Request logging middleware ───────────────────────────
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log every request with method, path, status, duration. Catch unhandled exceptions."""
    start = time.perf_counter()
    path = request.url.path
    method = request.method

    # Skip noisy polling endpoints from logs
    skip_log = path.endswith("/status") and method == "GET"

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        if not skip_log:
            logger.info(
                "%s %s → %d (%.0fms)",
                method, path, response.status_code, duration_ms,
            )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        logger.error(
            "%s %s → 500 UNHANDLED (%.0fms): %s\n%s",
            method, path, duration_ms, exc, traceback.format_exc(),
        )
        # 生产环境不暴露内部错误细节
        return JSONResponse(
            {"detail": "Internal Server Error"},
            status_code=500,
        )

# Legacy static dir (kept for backward compatibility)
STATIC_DIR = Path(__file__).parent / "static"

# Vue SPA dist directory (web/dist/ at project root)
DIST_DIR = Path(__file__).parents[3] / "web" / "dist"

# Serve Vue SPA build if available (production mode)
if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def spa_fallback(full_path: str):
        """Serve the Vue SPA for all non-API routes."""
        # Don't intercept API or WebSocket routes
        if full_path.startswith("api/") or full_path.startswith("ws"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return (DIST_DIR / "index.html").read_text(encoding="utf-8")
else:
    # Fallback: serve the legacy single-file dashboard
    @app.get("/", response_class=HTMLResponse)
    async def index():
        return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# V3: Event broadcast loop — consumes pipeline events and broadcasts to WebSocket clients
async def _broadcast_loop():
    """Consume events from the pipeline queue and broadcast to WebSocket clients."""
    q = get_event_queue()
    while True:
        try:
            event = await q.get()
            await manager.broadcast(event)
        except Exception:
            await asyncio.sleep(0.1)


@app.on_event("startup")
async def startup():
    """Start the WebSocket broadcast loop on app startup."""
    asyncio.create_task(_broadcast_loop())
