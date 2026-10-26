# Glossary and governance: phase one

Status: proposed code, not deployed or operationally verified. Tests are supplied but have not been run by the authoring assistant.

This additive prototype introduces bounded action states, request binding, authorization expiry, and receipts. It does not import the full 26-section glossary, modify the DAG, or protect existing execution paths. The companion JSON registry contains only the terms used in this prototype. Full glossary import and validation remain follow-up work.

## Canonical contracts

- Logical action: one intended operation, independent of attempt count.
- Authorization: permission for an exact action, target, parameters, tenant, policy revision, and validity period.
- Binding: compare a normalized request digest before entering execution.
- Receipt: record an observed outcome, not proof of all downstream effects.
- Uncertain: an external effect cannot yet be established; never automatically treat it as failure or retry permission.

## Prototype use

Create an ActionLedger within a trusted process. Register a proposal, authorize it through trusted application code, and call begin with the exact proposal before invoking an external adapter. Finish with an observed outcome. Adapter invocation is not automatic.

The ledger stores normalized proposal snapshots rather than mutable caller dictionaries. Its lock serializes lifecycle mutations within one process. It is not durable or distributed, and its authorization method does not authenticate approvers. Approval records are internal trusted-process state, not signed credentials. Do not expose authorize directly to untrusted callers.

An action can begin once. No retries or reconciliation transitions are implemented. A crash can lose all records. Unknown outcomes require operator handling. Receipt timestamps record local observation, not provider confirmation. Tenant ownership, provider idempotency, revocation, durable storage, policy enforcement integration, recovery, and production identity are future requirements.

## Validation

Run: python -m unittest discover -s tests -p test_action_contracts.py

No claim of formal proof, compliance certification, production safety, or end-to-end authorization is made.
