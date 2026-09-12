from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.enterprise_status import GARCAR_ENTERPRISE_SYSTEMS, build_enterprise_status

SYSTEM = "autonomous-orchestrator-core"
ROLE = "master_orchestrator"
VERSION = "1.0.0"
CONTRACT_VERSION = "1.0.0"

app = FastAPI(title="Autonomous Orchestrator Core", version=VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_events: deque[dict[str, Any]] = deque(maxlen=1000)
_counters: dict[str, int] = {
    "requests_total": 0,
    "health_checks": 0,
    "meta_checks": 0,
    "metrics_checks": 0,
    "events_checks": 0,
    "status_checks": 0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/")
def root():
    _counters["requests_total"] += 1
    return {
        "system": "Autonomous Orchestrator Core",
        "version": VERSION,
        "status": "operational",
        "author": "Garrett Carrol",
        "organization": "Garcar Enterprise",
        "managed_systems": 332,
        "priority_integrations": [system["repo"] for system in GARCAR_ENTERPRISE_SYSTEMS],
        "status_endpoint": "/status",
        "capabilities": [
            "enterprise-orchestration",
            "event-bus",
            "state-sync",
            "health-matrix",
            "autonomous-execution",
        ],
    }


@app.get("/health")
def health():
    _counters["health_checks"] += 1
    _counters["requests_total"] += 1
    return {
        "status": "healthy",
        "system": SYSTEM,
        "version": VERSION,
        "timestamp": _now(),
    }


@app.get("/meta")
def meta():
    _counters["meta_checks"] += 1
    _counters["requests_total"] += 1
    return {
        "system": SYSTEM,
        "role": ROLE,
        "contract_version": CONTRACT_VERSION,
        "endpoints": ["/health", "/meta", "/metrics", "/events"],
        "event_bus_topic_schema": "garcar.{system}.{event_type}",
    }


@app.get("/metrics")
def metrics():
    _counters["metrics_checks"] += 1
    _counters["requests_total"] += 1
    return dict(_counters)


@app.get("/events")
def events():
    _counters["events_checks"] += 1
    _counters["requests_total"] += 1
    ev = list(_events)
    return {"events": ev, "total": len(ev)}


@app.get("/status")
def status():
    _counters["status_checks"] += 1
    _counters["requests_total"] += 1
    return build_enterprise_status()
