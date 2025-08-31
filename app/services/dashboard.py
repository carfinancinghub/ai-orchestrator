# Path: app/services/dashboard.py
from __future__ import annotations
import json, statistics, os

try:
    import requests
except Exception:
    requests = None

def load_metrics(metrics_path: str = "audit_metrics.jsonl") -> dict:
    totals = {"files": 0, "PASS": 0, "FAIL": 0, "ERROR": 0}
    latencies = []
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                totals["files"] += 1
                st = obj.get("status", "ERROR")
                totals[st] = totals.get(st, 0) + 1
                if "latency" in obj:
                    latencies.append(float(obj["latency"]))
    except FileNotFoundError:
        pass
    if latencies:
        totals["latency_avg"] = round(statistics.mean(latencies), 3)
        totals["latency_p95"] = round(statistics.quantiles(latencies, n=20)[18], 3) if len(latencies) > 5 else max(latencies)
    else:
        totals["latency_avg"] = 0.0
        totals["latency_p95"] = 0.0
    return totals

def notify_slack(message: str):
    hook = os.getenv("SLACK_WEBHOOK","")
    if not hook or requests is None:
        return
    try:
        requests.post(hook, json={"text": message}, timeout=10)
    except Exception:
        pass
