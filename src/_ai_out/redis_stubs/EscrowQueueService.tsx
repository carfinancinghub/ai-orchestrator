/**
 * EscrowQueueService — Phase 3
 * - Default: in-memory adapter (no external deps)
 * - If CFH_REDIS_ESCROW=1, prefer Redis adapter (lazy import)
 */

export type EscrowJob = {
  id: string;
  createdAt: string;   // ISO
  payload: unknown;
  attempts: number;
  status: "queued" | "processing" | "acked" | "failed";
  failReason?: string;
};

export interface IEscrowQueue {
  enqueue(payload: unknown): Promise<EscrowJob>;
  dequeue(): Promise<EscrowJob | null>;
  ack(id: string): Promise<void>;
  fail(id: string, reason: string): Promise<void>;
  stats(): Promise<{ queued: number; processing: number; acked: number; failed: number }>;
}

class InMemoryEscrowQueue implements IEscrowQueue {
  private q: EscrowJob[] = [];
  private processing = new Map<string, EscrowJob>();
  private acked = 0;
  private failed = 0;

  async enqueue(payload: unknown): Promise<EscrowJob> {
    const job: EscrowJob = {
      id: cryptoRandomId(),
      createdAt: new Date().toISOString(),
      payload,
      attempts: 0,
      status: "queued",
    };
    this.q.push(job);
    return job;
  }

  async dequeue(): Promise<EscrowJob | null> {
    const job = this.q.shift() ?? null;
    if (!job) return null;
    job.status = "processing";
    job.attempts += 1;
    this.processing.set(job.id, job);
    return job;
  }

  async ack(id: string): Promise<void> {
    const job = this.processing.get(id);
    if (job) {
      job.status = "acked";
      this.processing.delete(id);
      this.acked += 1;
    }
  }

  async fail(id: string, reason: string): Promise<void> {
    const job = this.processing.get(id);
    if (job) {
      job.status = "failed";
      job.failReason = reason;
      this.processing.delete(id);
      this.failed += 1;
    }
  }

  async stats() {
    return {
      queued: this.q.length,
      processing: this.processing.size,
      acked: this.acked,
      failed: this.failed,
    };
  }
}

// --- async factory with flag-gated Redis ---
export async function getEscrowQueue(): Promise<IEscrowQueue> {
  const REDIS_FLAG = process.env.CFH_REDIS_ESCROW === "1";
  if (REDIS_FLAG) {
    const url = process.env.REDIS_URL || "redis://localhost:6379/0";
    try {
      const mod = await import("./RedisEscrowQueue");
      return new mod.RedisEscrowQueue(url);
    } catch (e) {
      console.warn("Redis adapter unavailable, falling back to in-memory. Reason:", e);
    }
  }
  return new InMemoryEscrowQueue();
}

// Small util without Node 18+ crypto import gymnastics
function cryptoRandomId(): string {
  // Not cryptographically strong; fine for job IDs in dev.
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}