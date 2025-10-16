from fastapi import APIRouter
import os, socket
from urllib.parse import urlparse
from datetime import datetime

router = APIRouter(prefix="/redis")

def _tcp_ping(url: str, timeout: float = 0.5) -> bool:
    try:
        u = urlparse(url)
        host = u.hostname or "localhost"
        port = u.port or 6379
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

@router.get("/health")
def redis_health():
    enabled = os.getenv("CFH_REDIS_ESCROW") == "1"
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    reachable = _tcp_ping(url) if enabled else False
    return {
        "ok": True,
        "ts": datetime.utcnow().isoformat() + "Z",
        "enabled": enabled,
        "url": url,
        "reachable": reachable,
    }