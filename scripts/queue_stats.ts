/**
 * Minimal shim: import queue & dump stats to console for wave scripts.
 * Later: replace with HTTP call to /redis/health once API endpoint exists.
 */
import { getEscrowQueue } from "../src/_ai_out/redis_stubs/EscrowQueueService.tsx";

async function main() {
  const q = getEscrowQueue();
  const s = await q.stats();
  // CSV-ish line for easy grep/append by existing wave tooling
  // ts, module, queued, processing, acked, failed
  const ts = new Date().toISOString();
  console.log(`${ts},escrow_queue,${s.queued},${s.processing},${s.acked},${s.failed}`);
}

main().catch(err => { console.error(err); process.exit(1); });