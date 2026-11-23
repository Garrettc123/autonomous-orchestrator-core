# RHNS DAG completion-evidence gate (draft release note)

## Why
`core/dag_orchestrator.py` previously returned `SUCCESS` for a worker that
returned `status: skipped`, `error`, or `triggered`, or when there was no
execution function. A GitHub workflow_dispatch HTTP 204 means the dispatch
was accepted; it does NOT prove the workflow ran, completed, or produced a
verified side effect.

## New result contract
- SUCCESS: a worker explicitly returns `ok`, `success`, `completed`, or
  `done` after verifying completion. Merely receiving a dispatch ack is
  insufficient.
- FAILED: the worker raises after bounded retries, has no executable handler,
  or explicitly returns an error/failure.
- SKIPPED: dependency requirements were not satisfied, or worker explicitly
  skipped execution.
- UNVERIFIED: dispatched/queued/pending, unknown, missing, or otherwise
  non-terminal result. Never grants downstream capabilities.

Critical FAILED, SKIPPED, or UNVERIFIED nodes halt the DAG.
Non-terminal returned outcomes are not automatically retried, to avoid
double-dispatch of externally accepted work.

## Known limitations / not yet certified
- Workflow dispatch adapters still do NOT poll GitHub for an exact
  completed workflow run or durable result receipt. Under the new gate, these
  actions remain UNVERIFIED and correctly cannot unlock the revenue chain.
- The market-intelligence adapter is still a placeholder and now reports
  unavailable; zero threats/opportunities is not asserted.
- DAG run state remains in memory. Durable idempotency, run IDs tied to
  external actions, and cross-process recovery require implementation.
- The main API `/health`, root's fixed `managed_systems`, and
  `build_enterprise_status()` remain separate unverified surfaces.
- Branch-protection requirements must be checked: the misleading
  `.github/workflows/ci-cd.yml` was removed on this branch because its
  validate/test/deploy/monitor jobs only printed success and fixed revenue.
  The actual `.github/workflows/ci.yml` and `rhns-dag-ci.yml` remain.

## Release acceptance
1. Run the full pytest suite and DAG-specific CI across supported Python versions.
2. Confirm any branch-protection check names affected by removing
   the echo-only workflow, without bypassing real required checks.
3. Implement workflow completion polling with an immutable dispatch correlation
   ID and a terminal, provider-verified result before marking those nodes SUCCESS.
4. Add a durable run ledger with task/tenant IDs, attempt IDs, outcome evidence,
   timeouts, approvals, and idempotency keys.
5. Prove a read-only end-to-end canary including a failure path, with no
   outbound actions or production credentials.
6. Only then consider production rollout by explicit approval.

No autonomous deployments, financial transactions, or external dispatches are
part of this draft PR.
