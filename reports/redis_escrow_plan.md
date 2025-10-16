---
title: EscrowQueueService
purpose: "Redis-backed notifications/disputes publisher"
labels: ["feature: message-queue-redis","pillar: escrow"]
tiering:
  free:     { summary: "publishEvent(txId,event,payload), health" }
  premium:  { validation: "retry/backoff, idempotency, bounded payload" }
  wow:      { extras: "fee-gated retries, metrics, tracing, DLQ" }
inputs:
  - { name: transactionId, type: string }
  - { name: event,         type: "created|funded|release|dispute|closed" }
  - { name: payload,       type: object }
outputs:
  - { name: queueId,       type: string }
  - { name: retryCount,    type: number }
deps:
  - "ioredis"            # stub/mocked
  - "@/services/escrow"  # logical dependency
confidence: 0.86
source: "design"
---
# EscrowQueueService
- publishEvent(txId,event,payload) → queueId
- exponential backoff; TODO: ioredis import + env config
