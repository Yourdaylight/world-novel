"""FastAPI web application for the novel creator dashboard."""

from __future__ import annotations

import asyncio
import json
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

app = FastAPI(title="WorldNovel Dashboard", version="0.5.0")

# CORS — allow local dev (Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


# ── Health endpoint ──────────────────────────────────────
@app.get("/api/health")
async def health():
    """Quick health check for smoke tests and monitoring."""
    return {"status": "ok", "version": "0.5.0"}


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
        return JSONResponse(
            {"detail": f"Internal Server Error: {exc}"},
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
