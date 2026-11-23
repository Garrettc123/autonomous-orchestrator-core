"""Durable, fail-closed GitHub workflow completion evidence.

The caller MUST obtain run metadata from an authenticated GitHub API client.
A dispatch HTTP 204 is never completion evidence. This store is not a
signature verifier or a replacement for the authenticated provider boundary.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


class WorkflowReceiptStore:
    """SQLite WAL receipt journal with exact dispatch-to-run correlation."""

    def __init__(self, db_path):
        self.path = str(Path(db_path))
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    ref_sha TEXT NOT NULL,
                    run_id INTEGER UNIQUE,
                    state TEXT NOT NULL DEFAULT 'unverified',
                    receipt TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def register(self, dispatch_id, tenant, repository, workflow, ref_sha):
        if not all((dispatch_id, tenant, repository, workflow, ref_sha)):
            raise ValueError("All dispatch identity fields are required")
        with self._connect() as db:
            existing = db.execute(
                "SELECT tenant,repository,workflow,ref_sha FROM dispatches "
                "WHERE dispatch_id=?", (dispatch_id,),
            ).fetchone()
            expected = (tenant, repository, workflow, ref_sha)
            if existing:
                if existing != expected:
                    raise ValueError("Dispatch ID reused with different identity")
                return False
            db.execute(
                "INSERT INTO dispatches "
                "(dispatch_id,tenant,repository,workflow,ref_sha,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (*((dispatch_id,) + expected), _now(), _now()),
            )
            return True

    def reconcile(self, dispatch_id, provider_run):
        """Accept only exact, terminal, authenticated-provider run metadata.

        The caller is responsible for fetching provider_run from GitHub,
        authenticating that response, and uniquely correlating its run ID to
        this dispatch. Ambiguous matching must never call this method.
        """
        required = ("id", "repository", "workflow", "head_sha", "status", "conclusion")
        if not isinstance(provider_run, dict) or any(
            provider_run.get(k) is None for k in required
        ):
            raise ValueError("Incomplete provider run evidence")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT repository,workflow,ref_sha,run_id,state "
                "FROM dispatches WHERE dispatch_id=?", (dispatch_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown dispatch")
            repo, workflow, sha, prior_run_id, prior_state = row
            run_id = provider_run["id"]
            if type(run_id) is not int or run_id <= 0:
                raise ValueError("Invalid provider run ID")
            if (repo, workflow, sha) != (
                provider_run["repository"], provider_run["workflow"],
                provider_run["head_sha"],
            ):
                raise ValueError("Provider run identity mismatch")
            if prior_run_id is not None and prior_run_id != run_id:
                raise ValueError("Dispatch already bound to another run")
            if prior_state in ("success", "failed"):
                return prior_state
            if provider_run["status"] != "completed":
                state = "unverified"
            elif provider_run["conclusion"] == "success":
                state = "success"
            else:
                state = "failed"
            receipt = json.dumps(provider_run, sort_keys=True)
            db.execute(
                "UPDATE dispatches SET run_id=?,state=?,receipt=?,updated_at=? "
                "WHERE dispatch_id=?",
                (run_id, state, receipt, _now(), dispatch_id),
            )
            return state

    def get(self, dispatch_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT state,run_id,receipt FROM dispatches WHERE dispatch_id=?",
                (dispatch_id,),
            ).fetchone()
        if row is None:
            return None
        return {"status": row[0], "run_id": row[1],
                "receipt": json.loads(row[2]) if row[2] else None}
