"""Garcar DAG never dispatches duplicate external work or invents outcomes."""
import pytest

from core import garcar_dag
from core.github_workflow_verifier import GitHubWorkflowVerifier
from core.workflow_receipts import WorkflowReceiptLedger


@pytest.mark.asyncio
async def test_no_receipt_prevents_implicit_dispatch(monkeypatch):
    monkeypatch.delenv("RHNS_RECEIPTS_DB", raising=False)
    monkeypatch.setattr(garcar_dag.requests, "post", lambda *a, **k: pytest.fail(
        "No external dispatch or message is permitted",
    ))
    defender = await garcar_dag.run_defender_os({"tenant_id": "tenant-a"})
    revenue = await garcar_dag.run_revenue_intelligence({"tenant_id": "tenant-a"})
    assert defender["status"] == "unverified"
    assert revenue["status"] == "unverified"


@pytest.mark.asyncio
async def test_wrong_tenant_cannot_reconcile_receipt(tmp_path, monkeypatch):
    path = tmp_path / "receipts.db"
    ledger = WorkflowReceiptLedger(path)
    ledger.reserve("d-one", "tenant-a", "Garrettc123/defender-os",
                   "status-report.yml", "main", "request-one")
    ledger.mark_accepted("d-one")
    monkeypatch.setenv("RHNS_RECEIPTS_DB", str(path))
    result = await garcar_dag.run_defender_os({
        "tenant_id": "tenant-b", "defender_dispatch_id": "d-one",
    })
    assert result["status"] == "unverified"
    assert result["reason"] == "tenant_or_receipt_mismatch"


@pytest.mark.asyncio
async def test_green_workflow_does_not_prove_defender_health(tmp_path, monkeypatch):
    path = tmp_path / "receipts.db"
    ledger = WorkflowReceiptLedger(path)
    ledger.reserve("d-two", "tenant-a", "Garrettc123/defender-os",
                   "status-report.yml", "main", "request-two")
    ledger.mark_accepted("d-two")
    monkeypatch.setenv("RHNS_RECEIPTS_DB", str(path))
    monkeypatch.setattr(GitHubWorkflowVerifier, "reconcile",
                        lambda self, dispatch_id, token: {
                            "status": "completed",
                            "scope": "github_workflow",
                            "business_outcome": "unverified",
                        })
    result = await garcar_dag.run_defender_os({
        "tenant_id": "tenant-a", "defender_dispatch_id": "d-two",
    })
    assert result["status"] == "unverified"
    assert result["workflow_status"] == "completed"
    assert result["reason"] == "business_outcome_not_proven"


@pytest.mark.asyncio
async def test_provider_failure_does_not_appear_successful(tmp_path, monkeypatch):
    path = tmp_path / "receipts.db"
    ledger = WorkflowReceiptLedger(path)
    ledger.reserve("d-three", "tenant-a", "Garrettc123/revenue-intelligence-engine",
                   "revenue-intelligence.yml", "main", "request-three")
    ledger.mark_accepted("d-three")
    monkeypatch.setenv("RHNS_RECEIPTS_DB", str(path))
    monkeypatch.setattr(GitHubWorkflowVerifier, "reconcile",
                        lambda self, dispatch_id, token: {"status": "failed"})
    result = await garcar_dag.run_revenue_intelligence({
        "tenant_id": "tenant-a", "revenue_dispatch_id": "d-three",
    })
    assert result["status"] == "failed"
