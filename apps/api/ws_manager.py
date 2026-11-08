"""STEP 11 — WebSocket fan-out. NOT executable here (fastapi/starlette not installed, no network).

Kept deliberately tiny: a list of live connections plus broadcast. `broadcast_sync` exists because
apps/api/pipeline.IngestionPipeline is synchronous (and is unit-tested that way, on purpose, so its
logic doesn't require an event loop to test) but FastAPI's WebSocket.send_json is a coroutine;
broadcast_sync schedules the send on the running loop via asyncio.create_task so main.py's synchronous
route handler can call it without becoming async itself. If no event loop is running (e.g. this module
imported outside of uvicorn), broadcast_sync degrades to a no-op rather than raising, so pipeline tests
that don't use FastAPI at all are unaffected.
"""
from __future__ import annotations
import asyncio
import json


class ConnectionManager:
    def __init__(self):
        self._connections: list = []
        self._event_loop = None  # bound at app startup so sync (threadpool) route handlers can broadcast

    def bind_loop(self, loop):
        self._event_loop = loop

    async def connect(self, websocket):
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket):
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_sync(self, message: dict):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            loop.create_task(self.broadcast(message))
            return
        # Called from a worker thread (FastAPI runs plain `def` routes in a threadpool): hand the
        # coroutine to the server's event loop thread-safely. No bound loop -> drop silently, never raise.
        if self._event_loop is not None and self._event_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self._event_loop)
