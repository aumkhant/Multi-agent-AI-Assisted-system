# Multi-agent-AI-Assisted-system

FastAPI multi-agent support assistant with Semantic Kernel routing, Postgres-backed
tools, and guardrails, built for the NetSol AI CoE take-home assignment.

See [`docs/design.md`](docs/design.md) for architecture, [`docs/implementation_plan.md`](docs/implementation_plan.md)
for the phased plan/checklist/limitations, and [`docs/ai_usage.md`](docs/ai_usage.md) for
how AI coding tools were used.

## Setup

### 1. Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Start Postgres and restore Pagila

```bash
docker compose up -d
./scripts/restore_pagila.sh
```

This downloads the [Pagila](https://github.com/devrimgunduz/pagila) schema and data
dumps and loads them into the `postgres` container.

### 3. Configure environment

```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY (a mini/nano-tier model is required, see the
# assignment's LLM key note - defaults to gpt-4o-mini)
```

### 4. Run migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

This adds `film.streaming_available` and creates `streaming_subscription` (seeded with
one active subscription for `customer_id=1` and one cancelled one for `customer_id=2`).

### 5. Run the app

```bash
uvicorn app.main:app --reload
```

```bash
curl -X POST localhost:8000/agent/respond \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "conversation_id": "conv_001", "message": "Is Alien available for streaming?"}'
```

### 6. Run tests

```bash
pytest
```

Tests do not require a live Postgres or OpenAI key - DB tools are tested against a
mocked session, and API tests override the LLM dependency for the safety-critical paths
that don't need a live model call. Running the examples in `evals/evals.json` against a
running server with a real DB + API key is the way to manually verify full end-to-end
behavior (including cases that do call the LLM).

## Project layout

```
app/            FastAPI app, config, DB session, orchestrator, agents, tools, guardrails
alembic/        Migrations (0001 streaming_available column, 0002 streaming_subscription)
knowledge_base/ Local markdown articles used by search_kb
evals/          10 eval examples (input, expected intent/agent/tools, safety behavior)
tests/          Tool, guardrail, and API tests
docs/           design.md, implementation_plan.md, ai_usage.md
scripts/        restore_pagila.sh
```
