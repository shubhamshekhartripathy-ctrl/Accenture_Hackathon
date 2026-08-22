"""In-process SSE event bus with a bounded per-run buffer (arch Q).

Emits ONLY safe operational progress ("Reconciliation complete") — never
internal chain-of-thought. Redis pub/sub upgrade lands with S10; until then
subscribers poll the buffer (simple, correct, thread-safe). Refresh never
loses state: buffered events are replayed to every new subscriber.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import Callable

BUFFER_LIMIT = 200

_lock = threading.Lock()
_buffers: dict[str, deque] = {}
_emit_id = 0


def emit(run_id: str, event: str, message: str, data: dict | None = None) -> None:
    global _emit_id
    with _lock:
        _emit_id += 1
        buf = _buffers.setdefault(run_id, deque(maxlen=BUFFER_LIMIT))
        buf.append({
            "id": _emit_id,
            "event": event,
            "message": message,
            "data": data or {},
        })


def buffered(run_id: str) -> list[dict]:
    with _lock:
        buf = _buffers.get(run_id)
        return list(buf) if buf else []


def has_event(run_id: str, event: str) -> bool:
    return any(e["event"] == event for e in buffered(run_id))


def drop(run_id: str) -> None:
    with _lock:
        _buffers.pop(run_id, None)
