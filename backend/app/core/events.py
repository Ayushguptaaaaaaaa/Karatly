"""Thread-safe in-memory pub/sub used for Server-Sent Events.

Topics: "global" (data_changed, job_finished, ai_status) and "job:<id>" (step/tool/done/error).
publish() may be called from CrewAI worker threads.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any

log = logging.getLogger("app.events")


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._lock:
            self._subs[topic].add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs[topic].discard(q)
            if not self._subs[topic]:
                self._subs.pop(topic, None)

    @staticmethod
    def _put(q: asyncio.Queue, item: dict) -> None:
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover
                pass
        q.put_nowait(item)

    def publish(self, topic: str, event: str, data: dict[str, Any]) -> None:
        item = {"event": event, "data": data}
        with self._lock:
            queues = list(self._subs.get(topic, ()))
        if not queues:
            return
        loop = self._loop
        for q in queues:
            try:
                if loop and loop.is_running():
                    try:
                        running = asyncio.get_running_loop()
                    except RuntimeError:
                        running = None
                    if running is loop:
                        self._put(q, item)
                    else:
                        loop.call_soon_threadsafe(self._put, q, item)
                else:
                    self._put(q, item)
            except Exception:  # pragma: no cover - never break the caller
                log.exception("Failed to publish %s on %s", event, topic)


bus = EventBus()
