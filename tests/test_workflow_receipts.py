"""Tests for durable RHNS provider completion receipts."""
import pytest

from core.workflow_receipts import WorkflowReceiptStore


def run(status="completed", conclusion="success", run_id=123):
    return {
        "id": run_id, "repository": "owner/repo", "workflow": "worker.yml",
        "head_sha": "a" * 40, "status": status, "conclusion": conclusion,
    }


def store(tmp_path):
    db = WorkflowReceiptStore(tmp_path / "receipts.db")
    assert db.register("dispatch-1", "tenant-a", "owner/repo", "worker.yml", "a" * 40)
    return db


def test_dispatch_idempotency_and_identity(tmp_path):
    db = store(tmp_path)
    assert not db.register("dispatch-1", "tenant-a", "owner/repo", "worker.yml", "a" * 40)
    with pytest.raises(ValueError, match="reused"):
        db.register("dispatch-1", "tenant-b", "owner/repo", "worker.yml", "a" * 40)


def test_accepted_dispatch_is_not_success(tmp_path):
    db = store(tmp_path)
    assert db.get("dispatch-1")["status"] == "unverified"
    assert db.reconcile("dispatch-1", run("in_progress", None)) == "unverified"


def test_terminal_success_persists_across_restart(tmp_path):
    db = store(tmp_path)
    assert db.reconcile("dispatch-1", run()) == "success"
    restored = WorkflowReceiptStore(tmp_path / "receipts.db")
    assert restored.get("dispatch-1")["status"] == "success"
    assert restored.get("dispatch-1")["run_id"] == 123


def test_terminal_failure_is_not_success(tmp_path):
    db = store(tmp_path)
    assert db.reconcile("dispatch-1", run(conclusion="failure")) == "failed"


@pytest.mark.parametrize("field,value", [
    ("repository", "other/repo"),
    ("workflow", "other.yml"),
    ("head_sha", "b" * 40),
    ("id", 0),
])
def test_wrong_run_identity_rejected(tmp_path, field, value):
    db = store(tmp_path)
    evidence = run()
    evidence[field] = value
    with pytest.raises(ValueError):
        db.reconcile("dispatch-1", evidence)
    assert db.get("dispatch-1")["status"] == "unverified"


def test_run_id_cannot_change(tmp_path):
    db = store(tmp_path)
    db.reconcile("dispatch-1", run("in_progress", None))
    with pytest.raises(ValueError, match="another run"):
        db.reconcile("dispatch-1", run(run_id=456))


def test_missing_provider_evidence_rejected(tmp_path):
    db = store(tmp_path)
    with pytest.raises(ValueError):
        db.reconcile("dispatch-1", {"status": "completed"})


def test_unknown_dispatch_rejected(tmp_path):
    db = store(tmp_path)
    with pytest.raises(ValueError, match="Unknown"):
        db.reconcile("unknown", run())
