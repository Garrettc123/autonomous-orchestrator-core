# Runtime secrets — where they go

Do not commit values. Do not paste values into issues, PRs, or chat.

## The spot

**Repository secrets (use this):**
https://github.com/Garrettc123/autonomous-orchestrator-core/settings/secrets/actions

Button: **New repository secret**

**Environment secrets (only if you also use the `production` environment):**
https://github.com/Garrettc123/autonomous-orchestrator-core/settings/environments

## Names to create

| Name | Required | What it is |
|---|---|---|
| `STRIPE_SECRET_KEY` | Yes | Live or test secret key from Stripe Dashboard → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | No | `whsec_...` from the webhook endpoint that hits this stack |
| `STRIPE_PAYMENT_LINK_URL` | No | Public Payment Link URL (not a secret, but kept here if you want one source) |
| `COMMANDER_ONE_KEY` | No | OneKey master seed; never store on disk outside this encrypted store |
| `APOLLO_API_KEY` | No | Lead source |

Do not add `PORT` or `NODE_ENV` as secrets. Those are config, not keys.

## After you save names

1. Open https://github.com/Garrettc123/autonomous-orchestrator-core/actions/workflows/secrets-presence.yml
2. Run workflow → `Secrets Presence`
3. The log must say `PRESENT length=N` for `STRIPE_SECRET_KEY` and must not print the value.

If the job says `MISSING`, the name was mistyped or saved in a different repo.
