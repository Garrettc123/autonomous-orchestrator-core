# Runtime secrets — Autokey / HashiCorp

Do not commit values. Do not paste values into issues, PRs, or chat.
Do not keep adding keys on every repo. One write plane, then sync.

## Source of truth

HashiCorp Vault in `systems-master-hub` (`vault/hashicorp/*`).
GitHub Actions secrets are a **distribution mirror** only.

Docs in hub:
- https://github.com/Garrettc123/systems-master-hub/blob/main/GARCAR-AUTOKEY.md
- https://github.com/Garrettc123/systems-master-hub/blob/main/vault/README.md

## The one spot (bootstrap once)

https://github.com/Garrettc123/systems-master-hub/settings/secrets/actions

Create these **control-plane** names first:

| Name | Why |
|---|---|
| `GHPAT` | PAT with `secrets:write` so Autokey can fan out to other repos |
| `VAULT_ADDR` | HashiCorp address (skip until a Vault process exists) |
| `VAULT_ROLE_ID` / `VAULT_SECRET_ID` | AppRole from `vault/hashicorp/bootstrap.sh` |
| or `VAULT_TOKEN` | Dev-only; prefer AppRole |

Then create vendor keys **once on this same hub page** (not on every repo):

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PAYMENT_LINK_URL` (optional)
- `APOLLO_API_KEY` (optional)
- `COMMANDER_ONE_KEY` (optional)

## Fire Autokey (no per-repo paste after that)

https://github.com/Garrettc123/systems-master-hub/actions/workflows/garcar-vault-sync.yml

| Mode | When |
|---|---|
| `github_only` | No Vault yet. Mint internal keys on GitHub. |
| `full` | Vault is up. Ingest hub secrets → Vault → sync to manifest repos. |
| `sync` | Vault already loaded. Fan-out only. |
| `dry_run` | Log only. |

Scheduled every 6 hours once control-plane secrets exist.

## This repo (`autonomous-orchestrator-core`)

After Autokey sync, this repo should receive mirrored names.
Presence check (values never printed):

https://github.com/Garrettc123/autonomous-orchestrator-core/actions/workflows/secrets-presence.yml

Direct repo secrets page (fallback only if hub sync cannot write):
https://github.com/Garrettc123/autonomous-orchestrator-core/settings/secrets/actions
