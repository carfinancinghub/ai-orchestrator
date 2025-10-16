# Escrow Queue — Redis Adapter
- Set `CFH_REDIS_ESCROW=1` to enable Redis-backed queue.
- Provide `REDIS_URL` (default: `redis://localhost:6379/0`).
- Factory `getEscrowQueue()` is async; update callers accordingly.

Install (dev only):
  npm i -D redis