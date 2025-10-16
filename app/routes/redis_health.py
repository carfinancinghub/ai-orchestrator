from __future__ import annotations

import os
import socket
from typing import Any, Dict
from urllib.parse import urlparse

from fastapi import APIRouter

# All endpoints under /redis/*
router = APIRouter(prefix="/redis")

def _parse_redis_url(url: str) -> tuple[str, int]:
    """
    Parse REDIS_URL (e.g., redis://localhost:6379/0) into (host, port).
    Falls back to ("localhost", 6379) on parse issues.
    """
    try:
        parts = urlparse(url)
        host = parts.hostname or "localhost"
        port = int(parts.port or 6379)
        return host, port
    except Exception:
        return "localhost", 6379

def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

@router.get("/health")
def redis_health() -> Dict[str, Any]:
    """
    Lightweight reachability signal. No hard dependency on redis-py.
    Returns whether the Redis TCP endpoint is reachable (when enabled).
    """
    enabled = bool(os.getenv("CFH_REDIS_ESCROW", "0") == "1")
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if not enabled:
        return {
            "ok": True,
            "ts": os.getenv("REQUEST_TS") or None,
            "enabled": False,
            "url": url,
            "reachable": False,
        }

    host, port = _parse_redis_url(url)
    reachable = _tcp_reachable(host, port, timeout=0.5)
    return {
        "ok": True,
        "ts": os.getenv("REQUEST_TS") or None,
        "enabled": True,
        "url": url,
        "reachable": bool(reachable),
    }

@router.get("/ping")
def redis_ping() -> Dict[str, Any]:
    """
    If CFH_REDIS_ESCROW=1 and REDIS_URL is reachable, measure round-trip latency
    using redis-py PING. Safe when disabled or SDK missing.
    """
    enabled = bool(os.getenv("CFH_REDIS_ESCROW", "0") == "1")
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if not enabled:
        return {
            "ok": False,
            "enabled": False,
            "reason": "redis_flag_disabled",
            "url": url,
        }

    try:
        import redis  # type: ignore
    except Exception:
        return {
            "ok": False,
            "enabled": True,
            "reason": "redis_sdk_missing",
            "url": url,
        }

    try:
        from time import perf_counter
        client = redis.Redis.from_url(
            url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        t0 = perf_counter()
        pong = client.ping()
        dt_ms = (perf_counter() - t0) * 1000.0
        return {
            "ok": bool(pong),
            "enabled": True,
            "latency_ms": round(dt_ms, 2),
            "url": url,
        }
    except Exception as e:
        return {
            "ok": False,
            "enabled": True,
            "reason": "redis_ping_failed",
            "detail": repr(e),
            "url": url,
        }