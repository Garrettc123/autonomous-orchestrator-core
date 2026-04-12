"""
Garcar Enterprise DAG Configuration
=====================================
Defines all AgentNode registrations for the Garcar Enterprise ecosystem.
This replaces run_all_systems.py with a dependency-aware execution graph.

Node categories (matching the 176-repo ecosystem):
  Layer 0 (no deps): Security & Defense, Infrastructure
  Layer 1 (depends on Layer 0): Market Intelligence, Revenue Monitoring
  Layer 2 (depends on Layer 1): AI SaaS, Commerce, Content
  Layer 3 (depends on Layer 2): Orchestration, Reporting, Notifications
"""

import asyncio
import logging
import os
import requests
from .dag_orchestrator import DAGOrchestrator, AgentNode

logger = logging.getLogger(__name__)


# ─── Node execution functions ──────────────────────────────────────────────

async def run_defender_os(ctx: dict) -> dict:
    """Trigger Defender OS health check via GitHub Actions API."""
    token = os.getenv("GH_PAT", "")
    if not token:
        return {"status": "skipped", "reason": "GH_PAT not set"}
    try:
        resp = requests.post(
            "https://api.github.com/repos/Garrettc123/defender-os/actions/workflows/status-report.yml/dispatches",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
            json={"ref": "main"},
            timeout=10,
        )
        return {"status": "triggered" if resp.status_code == 204 else "error", "http": resp.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def run_revenue_intelligence(ctx: dict) -> dict:
    """Trigger RHNS Revenue Intelligence cycle."""
    token = os.getenv("GH_PAT", "")
    if not token:
        return {"status": "skipped", "reason": "GH_PAT not set"}
    try:
        resp = requests.post(
            "https://api.github.com/repos/Garrettc123/revenue-intelligence-engine/actions/workflows/revenue-intelligence.yml/dispatches",  # noqa: E501
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
            json={"ref": "main"},
            timeout=10,
        )
        return {"status": "triggered" if resp.status_code == 204 else "error", "http": resp.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def run_harmony_score(ctx: dict) -> dict:
    """Compute the RHNS Harmony Score from node results in context."""
    results = {k: v for k, v in ctx.items() if k.startswith("result_")}
    total = len(results)
    if total == 0:
        return {"harmony_score": 0.0, "systems_online": 0}
    succeeded = sum(1 for r in results.values() if r.get("status") in ("triggered", "success", "ok"))
    score = succeeded / total
    logger.info(f"🎯 RHNS Harmony Score: {score:.3f} ({succeeded}/{total} systems nominal)")
    return {"harmony_score": score, "systems_online": succeeded, "systems_total": total}


async def run_market_intelligence(ctx: dict) -> dict:
    """Placeholder for market intelligence scan."""
    return {"status": "ok", "threats_detected": 0, "opportunities": 0}


async def run_slack_broadcast(ctx: dict) -> dict:
    """Post orchestration summary to Slack."""
    webhook = os.getenv("DEFENDER_SLACK_WEBHOOK", "")
    if not webhook:
        return {"status": "skipped"}

    harmony = ctx.get("result_harmony_score", {}).get("harmony_score", 0)
    systems = ctx.get("result_harmony_score", {}).get("systems_online", 0)

    msg = f"🌈 *RHNS DAG Cycle Complete* | Harmony: {harmony:.2f} | {systems} systems nominal"
    try:
        requests.post(webhook, json={"text": msg}, timeout=5)
        return {"status": "sent", "message": msg}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ─── Build the Garcar DAG ──────────────────────────────────────────────────

def build_garcar_dag() -> DAGOrchestrator:
    """Build and return the fully-wired Garcar Enterprise DAG."""

    dag = DAGOrchestrator(max_parallelism=8)

    # ── LAYER 0: Security & Infrastructure (no dependencies) ──────────────
    dag.register(AgentNode(
        node_id="defender_os",
        name="Defender OS Health Check",
        description="Triggers the 15-agent zero-trust defense system",
        provides=["defense_state", "security_baseline"],
        requires=[],
        consumes=[],
        emits=["defense_state"],
        priority=1,
        critical=True,
        timeout_s=15,
        execute_fn=run_defender_os,
    ))

    dag.register(AgentNode(
        node_id="market_intel",
        name="Market Intelligence Scan",
        description="Scans competitor landscape for threats and opportunities",
        provides=["market_signals"],
        requires=[],
        consumes=[],
        emits=["market_signals"],
        priority=2,
        timeout_s=20,
        execute_fn=run_market_intelligence,
    ))

    # ── LAYER 1: Revenue & Intelligence (depends on security baseline) ─────
    dag.register(AgentNode(
        node_id="revenue_intelligence",
        name="RHNS Revenue Intelligence",
        description="Hourly revenue cycle: Stripe + HubSpot signal processing",
        provides=["revenue_signals", "payment_state"],
        requires=["defense_state"],
        consumes=["market_signals"],
        emits=["revenue_signals"],
        priority=1,
        timeout_s=30,
        execute_fn=run_revenue_intelligence,
    ))

    # ── LAYER 2: Harmony Scoring (depends on revenue + market signals) ─────
    dag.register(AgentNode(
        node_id="harmony_score",
        name="RHNS Harmony Score",
        description="Computes system-wide harmony score from all node outcomes",
        provides=["harmony_state"],
        requires=["revenue_signals", "defense_state"],
        consumes=["revenue_signals", "market_signals"],
        emits=["harmony_state"],
        priority=2,
        timeout_s=5,
        execute_fn=run_harmony_score,
    ))

    # ── LAYER 3: Notifications (depends on harmony score) ──────────────────
    dag.register(AgentNode(
        node_id="slack_broadcast",
        name="Slack Orchestration Broadcast",
        description="Posts DAG cycle summary to Slack with harmony score",
        provides=["notification_sent"],
        requires=["harmony_state"],
        consumes=["harmony_state"],
        emits=[],
        priority=3,
        timeout_s=8,
        execute_fn=run_slack_broadcast,
    ))

    return dag


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")

    dag = build_garcar_dag()
    print(dag.visualize())

    result = asyncio.run(dag.run())
    print(f"\nResult: {result.succeeded}/{result.total_nodes} succeeded in {result.total_duration_ms:.0f}ms")
    if result.halted_early:
        print(f"HALTED: {result.halt_reason}")
