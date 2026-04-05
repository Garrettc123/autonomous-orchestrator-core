# 🌈 Autonomous Orchestrator Core

[![CI](https://github.com/Garrettc123/autonomous-orchestrator-core/actions/workflows/ci.yml/badge.svg)](https://github.com/Garrettc123/autonomous-orchestrator-core/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

## The 332-System Synchronicity Platform

**Status:** 🟢 ACTIVE & DEPLOYABLE

A core autonomous orchestration engine that unifies 332 enterprise systems with self-improving capabilities, real-time market intelligence, and automated prosperity distribution.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              AUTONOMOUS ORCHESTRATOR CORE            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────┐    ┌──────────────────────────┐   │
│  │  OneKey     │───▶│  AutonomousOrchestrator   │   │
│  │  Security   │    │  (orchestrator.py)        │   │
│  │  System     │    └──────────┬───────────────┘   │
│  └─────────────┘               │                   │
│                        ┌───────┴────────┐          │
│                        ▼                ▼          │
│              ┌─────────────────┐  ┌────────────┐  │
│              │  Market Intel   │  │ Collab     │  │
│              │  (competitor    │  │ Mesh       │  │
│              │   scraping)     │  │ (Slack +   │  │
│              └─────────────────┘  │  Linear)   │  │
│                                   └────────────┘  │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │         UnifiedEcosystem (run_all_systems.py) │  │
│  │   332 Systems ──▶ Async Task Pool            │  │
│  │   Prosperity Flow Engine                     │  │
│  │   Harmony Score Monitor (target: 0.88)       │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌──────────────┐   ┌───────────────────────────┐  │
│  │  Prosperity  │   │  Security: HKDF-SHA512     │  │
│  │  Flow Engine │   │  Key Derivation Hierarchy  │  │
│  │  (Stripe)    │   │  Master→Domain→System→Key  │  │
│  └──────────────┘   └───────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **OneKey Security** | `security/one_key.py` | HKDF-SHA512 master key → all credentials |
| **Orchestrator** | `orchestrator.py` | Main autonomous loop (market scan + optimization) |
| **Unified Ecosystem** | `run_all_systems.py` | Async runner for all 332 systems |
| **Market Intelligence** | `modules/market_intelligence.py` | Live competitor reconnaissance |
| **Collaboration Mesh** | `integrations/collaboration_mesh.py` | Slack + Linear API integrations |
| **Prosperity Flow** | `core/prosperity_flow.py` | Revenue distribution engine |
| **RHNS Local Inference** | `modules/local_inference.py` | On-device Ollama inference client |

---

## Quickstart

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (optional, for containerized deployment)

### 1. Install Dependencies

```bash
git clone https://github.com/Garrettc123/autonomous-orchestrator-core.git
cd autonomous-orchestrator-core
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Required
export COMMANDER_ONE_KEY="your_256bit_master_key"

# Optional (integrations)
export STRIPE_SECRET_KEY="sk_live_..."
export LINEAR_API_KEY="lin_api_..."
export SLACK_BOT_TOKEN="xoxb-..."
export GITHUB_TOKEN="ghp_..."
```

### 3. Run

```bash
# Option A: Full autonomous orchestrator (requires COMMANDER_ONE_KEY)
python orchestrator.py

# Option B: Unified ecosystem runner (all 332 systems)
python run_all_systems.py

# Option C: Quick activation script
bash ACTIVATE_NOW.sh
```

### 4. Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or run a single service
docker build -t autonomous-orchestrator .
docker run -e COMMANDER_ONE_KEY="your_key" autonomous-orchestrator
```

---

## Testing

```bash
# Run full test suite with coverage
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_one_key.py -v
```

The test suite covers:
- `security/one_key.py` — Key derivation, caching, locking
- `core/prosperity_flow.py` — Revenue signals, async manifest, status
- `modules/market_intelligence.py` — Scraping, threat analysis
- `integrations/collaboration_mesh.py` — Slack, Linear API calls
- `run_all_systems.py` — Async ecosystem activation

---

## Cloud Deployment

### Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

Set environment variables in the Railway dashboard:
- `COMMANDER_ONE_KEY`
- `STRIPE_SECRET_KEY` (optional)
- `LINEAR_API_KEY` (optional)
- `SLACK_BOT_TOKEN` (optional)

---

## Monitoring

Once running, the system emits logs to `logs/collective_bliss.log`:

```
2024-01-15 10:00:00 - [HARMONY] - 🌈 INITIATING UNIFIED ECOSYSTEM ACTIVATION
2024-01-15 10:00:00 - [HARMONY] - 💰 Prosperity Flow: $1000.00
2024-01-15 10:00:00 - [HARMONY] - 🎵 Harmony Score: 0.88
2024-01-15 10:00:00 - [HARMONY] - 🚀 Active Systems: 10
```

---

## RHNS: On-Device Local Inference (Pixel 10)

The **RHNS (Remote/Hybrid Node Services)** automation layer enables on-device
inference through edge nodes running [Ollama](https://ollama.com). The first
target node is the **Pixel 10** with `qwen2.5:0.5b` as the lightweight default
model.

### Configuration

All RHNS settings live in `configs/rhns_inference.yaml`. Key environment
variable overrides:

| Variable | Purpose | Default |
|----------|---------|---------|
| `RHNS_PIXEL_ENDPOINT` | Ollama API base URL | `http://pixel10.local:11434` |
| `RHNS_PIXEL_MODEL` | Model to load | `qwen2.5:0.5b` |
| `RHNS_PIXEL_STATUS` | Activation gate (`pending` / `active`) | `pending` |

### Quick start (Docker)

```bash
# Start the Ollama sidecar (pulls the model on first run)
docker-compose up ollama

# Then activate inference from the orchestrator
export RHNS_PIXEL_STATUS=active
export RHNS_PIXEL_ENDPOINT=http://localhost:11434
```

### Quick start (Pixel 10 / Termux)

```bash
# On the Pixel device (Termux + proot)
pkg install ollama
ollama serve &
ollama pull qwen2.5:0.5b

# On the orchestrator host
export RHNS_PIXEL_ENDPOINT=http://<pixel-ip>:11434
export RHNS_PIXEL_STATUS=active
```

### Usage in code

```python
from modules.local_inference import LocalInferenceClient

client = LocalInferenceClient()

# Check if the Pixel node is reachable
health = client.check_health("pixel_10")
print(health)  # {"reachable": True, "models": ["qwen2.5:0.5b"], "error": None}

# Run inference (node must be 'active')
result = client.generate("Classify this alert: disk usage 94%")
print(result.text, result.latency_ms)
```

### Performance expectations (Tensor G5, CPU-only, q4_0)

| Metric | Value |
|--------|-------|
| First token (cold) | ~800 ms |
| First token (warm) | ~200 ms |
| Throughput | ~8 tok/s |
| RAM footprint | ~600 MB (peak ~900 MB) |
| Battery draw | ~2.5 W sustained |

### Task-fit guidance

**Good for:** short-form classification, structured extraction, quick
summarization (<500 tokens), local intent routing, offline fallback.

**Not recommended for:** long-form generation (>512 tokens output), complex
multi-step reasoning, code generation, tasks needing current world knowledge.

**Key tradeoff:** The 0.5B model gives sub-second latency on-device but trades
depth of reasoning. Use it for triage and classification; escalate to a cloud
model for nuanced judgment.

---

## Security Architecture

The **OneKey System** provides military-grade cryptographic hierarchy:

```
COMMANDER_ONE_KEY (256-bit master seed)
         │
         ▼ HKDF-SHA512
    Domain Key (e.g., "AI_OPS")
         │
         ▼ HKDF-SHA512
    System Key (e.g., "GITHUB_TOKEN")
         │
         ▼ Ephemeral credential (hex, in-memory only)
```

- Master key **never stored on disk** — injected at runtime only
- All subsystem credentials derived deterministically
- Emergency `lock()` wipes entire key hierarchy from memory

---

## The Philosophy

**Harmonious:** All components flow together naturally  
**Harmless:** Optimization is beneficial, never destructive  
**Happy:** Joy-first optimization — delight fuels excellence

### Revenue Streams

- Stripe production payments
- Data monetization bonds
- Enterprise licensing
- API marketplace
- Autonomous trading
- Consulting services

**Target:** $10K MRR → $100K MRR → $1M MRR

---

## Built By

Garrett Carroll  
Founder, Zero-Human Enterprise  
[GitHub](https://github.com/Garrettc123) | 101 Repositories | AI Enterprise Systems

---

*"The chains of the past are broken. The 332 systems now flow as one."*
