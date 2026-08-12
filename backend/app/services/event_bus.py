"""WebSocket event hub with Redis publication for multi-instance deployments."""
from __future__ import annotations

import asyncio
import json
from typing import Any
import uuid

from fastapi import WebSocket


class EventBus:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.connections: set[WebSocket] = set()
        self.connection_scopes: dict[WebSocket, list[str] | None] = {}
        self._redis = None
        self._listener_task: asyncio.Task | None = None
        self._origin = uuid.uuid4().hex

    async def connect(self, websocket: WebSocket, site_scopes: list[str] | None = None) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        self.connection_scopes[websocket] = site_scopes

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)
        self.connection_scopes.pop(websocket, None)

    async def _redis_client(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as redis
            client = redis.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            return client
        except Exception:
            return None

    async def _broadcast(self, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in tuple(self.connections):
            try:
                scopes = self.connection_scopes.get(websocket)
                site_id = event.get("site_id")
                if site_id and scopes is not None and "*" not in scopes and site_id not in scopes:
                    continue
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "event_id": uuid.uuid4().hex, **payload}
        await self._broadcast(event)
        client = await self._redis_client()
        if client:
            try:
                await client.publish("nexusai:operations", json.dumps({**event, "_origin": self._origin}, default=str))
            except Exception:
                self._redis = None

    async def start(self) -> None:
        """Listen for events from other API instances when Redis is available."""
        client = await self._redis_client()
        if client and self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen(client))

    async def _listen(self, client) -> None:
        pubsub = client.pubsub()
        try:
            await pubsub.subscribe("nexusai:operations")
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    event = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if event.pop("_origin", None) != self._origin:
                    await self._broadcast(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Local WebSocket delivery remains available when Redis disappears.
            self._redis = None
        finally:
            await pubsub.aclose()

    async def close(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._redis:
            await self._redis.aclose()
