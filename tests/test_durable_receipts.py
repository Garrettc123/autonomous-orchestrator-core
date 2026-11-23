"""Offline acceptance tests for durable workflow receipt correlation."""
import pytest

from core.durable_receipts import DurableReceiptRegistry, ReceiptConflict


def registry(tmp_path):
    return DurableReceiptRegistry(tmp_path / "receipts.db")


def identity():
    return dict(tenant_id="tenant-a", repository="owner/repo",
                workflow="deploy.yml", commit_sha="abc123", run_id=42)


def test_reopen_and_reconcile_success(tmp_path):
    r = registry(tmp_path)
    assert r.register("dispatch-1", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    assert not r.register("dispatch-1", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    r.bind_run("dispatch-1", 42)
    assert registry(tmp_path).status("dispatch-1")["state"] == "running"
    assert registry(tmp_path).observe(
        "dispatch-1", **identity(), provider_status="in_progress", conclusion=None
    ) == "unverified"
    assert registry(tmp_path).observe(
        "dispatch-1", **identity(), provider_status="completed", conclusion="success"
    ) == "success"
    assert registry(tmp_path).status("dispatch-1")["state"] == "success"


def test_reject_cross_tenant_and_wrong_sha(tmp_path):
    r = registry(tmp_path)
    r.register("dispatch-1", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    r.bind_run("dispatch-1", 42)
    with pytest.raises(ReceiptConflict):
        r.observe("dispatch-1", **{**identity(), "tenant_id": "tenant-b"},
                  provider_status="completed", conclusion="success")
    with pytest.raises(ReceiptConflict):
        r.observe("dispatch-1", **{**identity(), "commit_sha": "other"},
                  provider_status="completed", conclusion="success")
    assert r.status("dispatch-1")["state"] == "running"


def test_failure_never_unlocks(tmp_path):
    r = registry(tmp_path)
    r.register("dispatch-1", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    r.bind_run("dispatch-1", 42)
    assert r.observe("dispatch-1", **identity(),
                     provider_status="completed", conclusion="failure") == "failed"
    with pytest.raises(ReceiptConflict):
        r.observe("dispatch-1", **identity(),
                  provider_status="completed", conclusion="success")


def test_duplicate_intent_and_run_conflicts(tmp_path):
    r = registry(tmp_path)
    r.register("a", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    with pytest.raises(ReceiptConflict):
        r.register("a", "tenant-b", "owner/repo", "deploy.yml", "abc123")
    r.bind_run("a", 42)
    with pytest.raises(ReceiptConflict):
        r.bind_run("a", 43)
    r.register("b", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    with pytest.raises(Exception):
        r.bind_run("b", 42)


def test_missing_or_nonterminal_evidence_is_unverified(tmp_path):
    r = registry(tmp_path)
    r.register("a", "tenant-a", "owner/repo", "deploy.yml", "abc123")
    r.bind_run("a", 42)
    assert r.observe("a", **identity(),
                     provider_status="completed", conclusion=None) == "unverified"
