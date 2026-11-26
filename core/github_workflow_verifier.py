"""Independent read-only GitHub workflow completion verification for RHNS.

A workflow_dispatch 204 is acceptance, not execution proof. This verifier never
dispatches a workflow and never infers a business outcome from a green CI job.
Expected run-name: RHNS/<opaque dispatch_id>. The target workflow must support
that run-name and its dispatch must be reserved in WorkflowReceiptLedger.
"""
import re
from datetime import datetime, timezone
from urllib.parse import quote

import requests


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+\.ya?ml$")


def _utc(value):
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class GitHubWorkflowVerifier:
    """Read GitHub's own run state and reconcile a previously accepted receipt."""

    def __init__(self, ledger, http=None):
        self.ledger = ledger
        self.http = http if http is not None else requests.Session()

    def _get(self, token, endpoint, params=None):
        response = self.http.get(
            "https://api.github.com" + endpoint,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Unexpected GitHub API response")
        return body

    @staticmethod
    def _matches(run, receipt):
        """Require correlated run identity, not merely matching status or time."""
        if not isinstance(run, dict):
            return False
        if run.get("display_title") != "RHNS/" + receipt["dispatch_id"]:
            return False
        if run.get("event") != "workflow_dispatch" or run.get("head_branch") != receipt["ref"]:
            return False
        if run.get("path", "").split("@")[0] != ".github/workflows/" + receipt["workflow"]:
            return False
        if run.get("repository", {}).get("full_name") != receipt["repo"]:
            return False
        if not isinstance(run.get("id"), int) or not run.get("head_sha"):
            return False
        if run.get("run_attempt") != 1:
            return False
        try:
            if _utc(run.get("created_at")) < _utc(receipt["created_at"]):
                return False
        except (ValueError, TypeError, OverflowError):
            return False
        return True

    def _find(self, receipt, token):
        owner, name = receipt["repo"].split("/", 1)
        base = ("/repos/" + quote(owner) + "/" + quote(name) +
                "/actions/workflows/" + quote(receipt["workflow"]) + "/runs")
        matches = []
        for page in range(1, 4):
            response = self._get(token, base, params={
                "event": "workflow_dispatch",
                "branch": receipt["ref"],
                "per_page": 100,
                "page": page,
            })
            runs = response.get("workflow_runs")
            if not isinstance(runs, list):
                raise ValueError("Missing provider run list")
            matches.extend(r for r in runs if self._matches(r, receipt))
            if len(runs) < 100:
                break
        return matches

    def reconcile(self, dispatch_id, token):
        """Return terminal workflow evidence only after authenticated API reads.

        An unavailable API, missing run, ambiguous run or mismatched identity
        remains UNVERIFIED and never initiates a new external side effect.
        """
        receipt = self.ledger.read(dispatch_id)
        if receipt is None:
            return {"status": "unverified", "reason": "receipt_not_found"}
        if receipt["state"] in ("completed", "failed"):
            return {"status": "completed" if receipt["state"] == "completed" else "failed",
                    "scope": "github_workflow", "receipt_id": dispatch_id}
        if receipt["state"] not in ("accepted", "running"):
            return {"status": "unverified", "reason": "dispatch_not_confirmed"}
        if not token:
            return {"status": "unverified", "reason": "github_token_missing"}
        if not REPO_RE.fullmatch(receipt["repo"]) or not WORKFLOW_RE.fullmatch(receipt["workflow"]):
            return {"status": "unverified", "reason": "invalid_workflow_identity"}
        try:
            if receipt["state"] == "accepted":
                matches = self._find(receipt, token)
                if len(matches) != 1:
                    return {"status": "unverified", "reason":
                            "correlation_ambiguous" if matches else "run_not_observed"}
                run_id = matches[0]["id"]
            else:
                run_id = receipt["provider_run_id"]
                if not isinstance(run_id, int):
                    return {"status": "unverified", "reason": "run_id_missing"}

            owner, name = receipt["repo"].split("/", 1)
            endpoint = ("/repos/" + quote(owner) + "/" + quote(name) +
                        "/actions/runs/" + str(run_id))
            run = self._get(token, endpoint)
            if not self._matches(run, receipt) or run["id"] != run_id:
                return {"status": "unverified", "reason": "provider_identity_mismatch"}
            if receipt["state"] == "accepted":
                self.ledger.bind_run(dispatch_id, run_id, run["head_sha"])
            elif receipt["head_sha"] != run["head_sha"]:
                return {"status": "unverified", "reason": "provider_sha_changed"}
            if run.get("status") != "completed":
                return {"status": "unverified", "reason": "workflow_not_terminal",
                        "provider_run_id": run_id}
            conclusion = run.get("conclusion")
            if conclusion not in ("success", "failure", "cancelled", "timed_out",
                                  "action_required", "skipped"):
                return {"status": "unverified", "reason": "unknown_conclusion"}
            evidence = {
                "provider": "github_actions",
                "run_id": run_id,
                "head_sha": run["head_sha"],
                "workflow_path": run["path"],
                "url": run.get("html_url", ""),
                "conclusion": conclusion,
                "run_attempt": run["run_attempt"],
            }
            result = self.ledger.reconcile(
                dispatch_id, run_id, run["head_sha"], "completed", conclusion, evidence,
            )
            return {
                "status": "completed" if result["state"] == "completed" else "failed",
                "scope": "github_workflow",
                "business_outcome": "unverified",
                "receipt_id": dispatch_id,
                "provider_run_id": run_id,
            }
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return {"status": "unverified", "reason": "provider_reconciliation_failed"}
