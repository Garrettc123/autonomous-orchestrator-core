"""Offline tests for durable RHNS provider workflow receipts."""
import sqlite3

import pytest

from core.workflow_receipts import WorkflowReceiptLedger


def reserve(ledger):
    return ledger.reserve("d-1", "tenant-a", "owner/repo", "worker.yml", "main", "key-1")


def test_receipt_survives_restart(tmp_path):
    path = tmp_path / "receipts.db"
    ledger = WorkflowReceiptLedger(path)
    assert reserve(ledger)["state"] == "reserved"
    assert WorkflowReceiptLedger(path).unresolved()[0]["dispatch_id"] == "d-1"


def test_duplicate_request_key_rejected(tmp_path):
    ledger = WorkflowReceiptLedger(tmp_path / "receipts.db")
    reserve(ledger)
    with pytest.raises(sqlite3.IntegrityError):
        ledger.reserve("d-2", "tenant-a", "owner/repo", "worker.yml", "main", "key-1")


def test_acceptance_not_success(tmp_path):
    ledger = WorkflowReceiptLedger(tmp_path / "receipts.db")
    reserve(ledger)
    ledger.mark_accepted("d-1")
    assert ledger.read("d-1")["state"] == "accepted"
    assert ledger.read("d-1")["conclusion"] is None


def test_completion_requires_bound_identity_and_evidence(tmp_path):
    ledger = WorkflowReceiptLedger(tmp_path / "receipts.db")
    reserve(ledger)
    ledger.mark_accepted("d-1")
    with pytest.raises(ValueError):
        ledger.reconcile("d-1", 123, "abc", "completed", "success", {"provider": "github"})
    ledger.bind_run("d-1", 123, "abc")
    with pytest.raises(ValueError):
        ledger.reconcile("d-1", 999, "abc", "completed", "success", {"provider": "github"})
    with pytest.raises(ValueError):
        ledger.reconcile("d-1", 123, "abc", "in_progress", None, {"provider": "github"})
    with pytest.raises(ValueError):
        ledger.reconcile("d-1", 123, "abc", "completed", "success", {})
    result = ledger.reconcile("d-1", 123, "abc", "completed", "success",
                              {"provider": "github", "run_id": 123})
    assert result["state"] == "completed"
    assert ledger.unresolved() == []
    with pytest.raises(ValueError):
        ledger.reconcile("d-1", 123, "abc", "completed", "success", {"run_id": 123})


def test_failed_provider_run_cannot_be_success(tmp_path):
    ledger = WorkflowReceiptLedger(tmp_path / "receipts.db")
    reserve(ledger)
    ledger.mark_accepted("d-1")
    ledger.bind_run("d-1", 123, "abc")
    result = ledger.reconcile("d-1", 123, "abc", "completed", "failure",
                              {"provider": "github", "run_id": 123})
    assert result["state"] == "failed"
    assert result["conclusion"] == "failure"
