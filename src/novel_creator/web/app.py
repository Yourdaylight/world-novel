"""FastAPI web application for the novel creator dashboard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from novel_creator.web.events import get_event_queue
from novel_creator.web.routes import router

app = FastAPI(title="Novel Creator Dashboard", version="0.4.0")
app.include_router(router, prefix="/api")

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
