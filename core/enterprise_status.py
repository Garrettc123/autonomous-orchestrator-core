"""
Garcar Enterprise integration status helpers.
"""

from __future__ import annotations

import os
from copy import deepcopy


GARCAR_ENTERPRISE_SYSTEMS = [
    {
        "repo": "garcar-payments",
        "name": "Stripe Revenue Pipeline",
        "required_env": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"],
        "signals": [
            "payment_intent.succeeded",
            "invoice.paid",
            "customer.subscription.created",
        ],
    },
    {
        "repo": "garcar-autonomous-wealth-system",
        "name": "Agent Orchestration Core",
        "required_env": ["APOLLO_API_KEY", "LINEAR_API_KEY"],
        "signals": ["verified_lead", "stripe_checkout_link", "linear_task_closed"],
    },
    {
        "repo": "autonomous-income-deployment",
        "name": "CI/CD Backbone",
        "required_env": ["GITHUB_TOKEN"],
        "signals": ["deploy_succeeded", "rollback_triggered"],
    },
    {
        "repo": "ai-business-platform",
        "name": "Intelligence Layer",
        "required_env": ["OPENAI_API_KEY"],
        "signals": ["dynamic_pricing", "upsell_offer", "churn_alert"],
    },
    {
        "repo": "NEXUS-AI-CORE",
        "name": "Commerce & Real Estate Engine",
        "required_env": ["NEXUS_STATUS_ENDPOINT"],
        "signals": ["property_score", "deal_pipeline_update"],
    },
    {
        "repo": "zeus-dashboard",
        "name": "Master Control Interface",
        "required_env": ["ZEUS_STATUS_ENDPOINT"],
        "signals": ["mrr_report", "arr_report", "conversion_report", "churn_report"],
    },
]


def _integration_entry(system: dict) -> dict:
    entry = deepcopy(system)
    missing_env = [name for name in system["required_env"] if not os.getenv(name)]
    entry["missing_env"] = missing_env
    entry["configured"] = not missing_env
    entry["status"] = "ready" if entry["configured"] else "pending"
    return entry


def build_enterprise_status(metrics: dict | None = None) -> dict:
    """
    Return a machine-readable Garcar Enterprise integration snapshot.
    """
    metrics = metrics or {}
    systems = [_integration_entry(system) for system in GARCAR_ENTERPRISE_SYSTEMS]

    lead_count = int(metrics.get("lead_count", 0) or 0)
    paid_customers = int(metrics.get("paid_customers", 0) or 0)
    mrr = float(metrics.get("mrr", 0.0) or 0.0)
    arr = float(metrics.get("arr", mrr * 12) or 0.0)
    conversion_rate = float(
        metrics.get(
            "conversion_rate",
            (paid_customers / lead_count) if lead_count else 0.0,
        )
    )
    churn_rate = float(metrics.get("churn_rate", 0.0) or 0.0)

    ready_systems = sum(1 for system in systems if system["configured"])
    return {
        "organization": "Garcar Enterprise",
        "systems": systems,
        "summary": {
            "total_systems": len(systems),
            "ready_systems": ready_systems,
            "pending_systems": len(systems) - ready_systems,
            "orchestration_loop_status": metrics.get("orchestration_loop_status", "idle"),
            "active_systems": int(metrics.get("active_systems", 0) or 0),
            "harmony_score": float(metrics.get("harmony_score", 0.0) or 0.0),
            "prosperity_flow": float(metrics.get("prosperity_flow", 0.0) or 0.0),
        },
        "kpis": {
            "mrr": mrr,
            "arr": arr,
            "lead_count": lead_count,
            "paid_customers": paid_customers,
            "conversion_rate": conversion_rate,
            "churn_rate": churn_rate,
        },
    }
