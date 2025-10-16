/**
 * EscrowQueueService — Phase 3 bootstrap
 * Default: in-memory adapter (no external deps). Real Redis sits behind CFH_REDIS_ESCROW.
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

// Feature flag gate (ensure you set CFH_REDIS_ESCROW=1 only when real Redis adapter is ready)
const REDIS_FLAG = process.env.CFH_REDIS_ESCROW === "1";

/**
 * TODO(redis): when CFH_REDIS_ESCROW=1, return a Redis-backed implementation.
 * For now, always return in-memory to keep CI/dev happy.
 */
export function getEscrowQueue(): IEscrowQueue {
  // Placeholder: detect REDIS_FLAG and swap implementation later.
  return new InMemoryEscrowQueue();
}

// Small util without Node 18+ crypto import gymnastics
function cryptoRandomId(): string {
  // Not cryptographically strong; fine for job IDs in dev.
  return Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
}