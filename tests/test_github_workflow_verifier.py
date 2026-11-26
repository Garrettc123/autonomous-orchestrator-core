"""Provider-only offline regression coverage for the RHNS GitHub verifier."""
import json

from core.github_workflow_verifier import GitHubWorkflowVerifier
from core.workflow_receipts import WorkflowReceiptLedger


class Reply:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class HTTP:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Reply(self.replies.pop(0))


def make_ledger(tmp_path):
    ledger = WorkflowReceiptLedger(tmp_path / "runs.db")
    ledger.reserve("opaque-123", "tenant-a", "Garrettc123/defender-os",
                   "status-report.yml", "main", "request-123")
    ledger.mark_accepted("opaque-123")
    return ledger


def provider_run(conclusion=None, status="in_progress"):
    return {
        "id": 221,
        "display_title": "RHNS/opaque-123",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": "abcdef123456",
        "path": ".github/workflows/status-report.yml@refs/heads/main",
        "repository": {"full_name": "Garrettc123/defender-os"},
        "run_attempt": 1,
        "created_at": "2099-01-01T00:00:00Z",
        "status": status,
        "conclusion": conclusion,
        "html_url": "https://github.com/Garrettc123/defender-os/actions/runs/221",
    }


def test_acceptance_cannot_count_as_completion(tmp_path):
    ledger = make_ledger(tmp_path)
    verifier = GitHubWorkflowVerifier(ledger, HTTP([{"workflow_runs": []}]))
    result = verifier.reconcile("opaque-123", "token-only-in-test")
    assert result["status"] == "unverified"
    assert ledger.read("opaque-123")["state"] == "accepted"


def test_correlated_terminal_success_is_workflow_only(tmp_path):
    ledger = make_ledger(tmp_path)
    run = provider_run("success", "completed")
    http = HTTP([{"workflow_runs": [run]}, run])
    result = GitHubWorkflowVerifier(ledger, http).reconcile("opaque-123", "token-only-in-test")
    assert result["status"] == "completed"
    assert result["scope"] == "github_workflow"
    assert result["business_outcome"] == "unverified"
    stored = ledger.read("opaque-123")
    assert stored["provider_run_id"] == 221
    assert json.loads(stored["evidence_json"])["head_sha"] == run["head_sha"]
    assert len(http.calls) == 2
    assert all("/actions/" in url for url, _ in http.calls)


def test_terminal_failure_remains_failure(tmp_path):
    ledger = make_ledger(tmp_path)
    run = provider_run("failure", "completed")
    result = GitHubWorkflowVerifier(ledger, HTTP([{"workflow_runs": [run]}, run])).reconcile(
        "opaque-123", "token-only-in-test",
    )
    assert result["status"] == "failed"
    assert ledger.read("opaque-123")["state"] == "failed"


def test_rejects_uncorrelated_or_replayed_provider_run(tmp_path):
    ledger = make_ledger(tmp_path)
    wrong = provider_run("success", "completed")
    wrong["display_title"] = "RHNS/some-other-id"
    result = GitHubWorkflowVerifier(ledger, HTTP([{"workflow_runs": [wrong]}])).reconcile(
        "opaque-123", "token-only-in-test",
    )
    assert result["status"] == "unverified"
    assert ledger.read("opaque-123")["provider_run_id"] is None


def test_rejects_rerun_attempt_and_wrong_branch(tmp_path):
    ledger = make_ledger(tmp_path)
    wrong = provider_run("success", "completed")
    wrong["run_attempt"] = 2
    assert GitHubWorkflowVerifier(ledger, HTTP([{"workflow_runs": [wrong]}])).reconcile(
        "opaque-123", "token-only-in-test",
    )["status"] == "unverified"
    wrong["run_attempt"] = 1
    wrong["head_branch"] = "other"
    assert GitHubWorkflowVerifier(ledger, HTTP([{"workflow_runs": [wrong]}])).reconcile(
        "opaque-123", "token-only-in-test",
    )["status"] == "unverified"


def test_running_receipt_survives_process_restart(tmp_path):
    ledger = make_ledger(tmp_path)
    running = provider_run()
    first = GitHubWorkflowVerifier(ledger, HTTP([
        {"workflow_runs": [running]}, running,
    ])).reconcile("opaque-123", "token-only-in-test")
    assert first["status"] == "unverified"
    assert ledger.read("opaque-123")["state"] == "running"

    terminal = provider_run("success", "completed")
    recovered = WorkflowReceiptLedger(tmp_path / "runs.db")
    final = GitHubWorkflowVerifier(recovered, HTTP([terminal])).reconcile(
        "opaque-123", "token-only-in-test",
    )
    assert final["status"] == "completed"
    assert recovered.unresolved() == []
