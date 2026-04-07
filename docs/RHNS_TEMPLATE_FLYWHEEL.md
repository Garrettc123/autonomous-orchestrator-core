# RHNS Template Flywheel

## Overview

Every completed client engagement is automatically archived as a parameterized RHNS template in Notion. This builds a compounding library of reusable playbooks — the same flywheel pattern Palantir uses with their ontology, but executed autonomously.

## Architecture

```
Engagement Completes
        │
        ▼
GitHub Actions Trigger
(workflow_dispatch / repository_dispatch / workflow_call)
        │
        ▼
archive_rhns_template.py
        │
        ├── Validates engagement data
        ├── Structures into RHNS layers
        ├── Parameterizes for reuse
        │
        ▼
Notion API → RHNS Template Library
        │
        ├── Template Name
        ├── Vertical / Revenue Range / Client Type
        ├── Reason layer (first-principles analysis)
        ├── Harmony layer (system alignment)
        ├── Navigation layer (execution path)
        ├── Standards layer (quality guardrails)
        ├── Parameters ({{PLACEHOLDERS}} for cloning)
        └── Outcome Summary (quantified results)
```

## Trigger Methods

### 1. Manual (GitHub UI)
Go to Actions → "RHNS Template Archiver" → Run workflow. Fill in the form fields.

### 2. Programmatic (API)
```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/Garrettc123/autonomous-orchestrator-core/dispatches \
  -d '{
    "event_type": "archive_engagement",
    "client_payload": {
      "template_name": "Revenue Leak Audit — GC $2-5M DFW",
      "vertical": "General Contractor",
      "revenue_range": "$1-5M",
      "client_type": "SMB",
      "product_used": "Starter Audit",
      "tags": ["revenue-leak", "pricing"],
      "reason": "...",
      "harmony": "...",
      "navigation": "...",
      "standards": "...",
      "outcome_summary": "...",
      "parameters": {"client_name": "{{CLIENT_NAME}}"}
    }
  }'
```

### 3. From Other Workflows (Reusable)
```yaml
jobs:
  post-engagement:
    uses: ./.github/workflows/archive-engagement.yml
    with:
      engagement_data_json: ${{ toJson(needs.engagement.outputs.data) }}
    secrets:
      NOTION_API_KEY: ${{ secrets.NOTION_API_KEY }}
```

## Setup

### Prerequisites
1. **Notion Integration Token**
   - Go to https://www.notion.so/my-integrations
   - Create integration named "RHNS Template Archiver"
   - Copy the Internal Integration Token
   - Share the "RHNS Template Library" database with the integration

2. **GitHub Secret**
   - Go to repo Settings → Secrets → Actions
   - Add `NOTION_API_KEY` with the integration token

## RHNS Template Structure

Each template captures the four RHNS layers as parameterized content:

| Layer | Purpose | Template Pattern |
|-------|---------|-----------------|
| **Reason** | What is the actual problem and leverage point? | Analysis framework with {{parameters}} for client-specific data |
| **Harmony** | How do the systems interact? | Interconnection map showing which fixes depend on each other |
| **Navigation** | What is the execution path? | Week-by-week sprint plan with tools and milestones |
| **Standards** | What quality bars prevent drift? | Quantified success criteria and red flags |

## Flywheel Economics

- **Engagement 1-10**: Templates are drafted from live client work
- **Engagement 10-50**: Templates are cloned and customized (70%+ reuse rate)
- **Engagement 50-200**: Templates become the product — clients buy the playbook
- **Engagement 200+**: Template library IS the vertical AI product (Palantir's ontology equivalent)

Each template's `Reuse Count` property tracks how many times it's been cloned, providing signal on which verticals and problem types have the highest demand.
