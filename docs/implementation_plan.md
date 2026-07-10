# Implementation plan (MVP1)

## Phases

1. **Scaffold** - `pyproject.toml`, `app/` package layout, `.env.example`, config via
   `pydantic-settings`.
2. **Database** - `docker-compose.yml` for Postgres, `scripts/restore_pagila.sh` to pull
   and load the Pagila schema+data dump, Alembic wired to `app.config.settings.database_url`.
3. **Migrations** - `0001_add_film_streaming_available` (column + seed data),
   `0002_create_streaming_subscription` (table + seed rows).
4. **Tools** - typed Pydantic input/output per tool, `ToolMetadata` (MCP-ready contract),
   `logged_tool_call` for structured logging. DB tools use SQLAlchemy Core with
   parameterized `text()` queries against the existing Pagila schema.
5. **Mock tools** - `search_kb` over `knowledge_base/*.md`, `create_handoff_ticket`
   in-memory.
6. **Agents** - Semantic Kernel `Kernel` + `OpenAIChatCompletion` service
   (`app/agents/llm.py`), one module per agent. Triage does LLM JSON classification with
   a deterministic keyword fallback. Specialists call their tool directly, then one LLM
   call to phrase the answer from the tool's JSON output.
7. **Guardrails** - deterministic input-side checks (`app/guardrails/checks.py`) run
   before triage; a rule-based `GuardrailAgent` review runs after the specialist answers.
8. **Orchestrator + API** - `app/orchestrator.py` sequences the above;
   `POST /agent/respond` in `app/main.py` returns the validated `AgentResponse`.
9. **Tests** - tool tests (mocked DB session + real KB/handoff mock stores), guardrail
   tests (pure functions), API tests (FastAPI `TestClient`, kernel dependency overridden
   so tests don't need a live OpenAI key; safety-critical paths are exercised
   end-to-end since they don't require the LLM).
10. **Evals** - `evals/evals.json`, 10 examples covering every required eval-table row
    plus two extra edge cases (catalog not-found, KB no-answer).
11. **Docs** - this plan, `docs/design.md`, `docs/ai_usage.md`, README setup steps.

## Checklist

- [x] Project scaffold, venv, dependencies install cleanly (`pip install -e ".[dev]"`)
- [x] Docker Compose Postgres + Pagila restore script
- [x] Alembic migrations 0001/0002 with seed data
- [x] `search_film_catalog`, `get_customer_streaming_subscription`,
      `get_customer_rental_history` (typed, MCP metadata, logged)
- [x] `search_kb`, `create_handoff_ticket` (typed, MCP metadata, logged)
- [x] TriageAgent, CatalogAgent, SubscriptionAgent, RentalHistoryAgent, KnowledgeAgent,
      HumanHandoffAgent, GuardrailAgent
- [x] Orchestrator + `POST /agent/respond` returning the required structured JSON
- [x] Deterministic guardrails: prompt injection, sensitive mutation, missing customer_id
- [x] Tests: tools, guardrails, API (19 tests, all passing without a live DB/LLM)
- [x] `evals/evals.json` with 10 examples
- [x] `docs/design.md`, `docs/implementation_plan.md`, `docs/ai_usage.md`, README

## Assumptions

- The grading environment can run Docker (for Postgres) and has outbound network access
  to fetch the Pagila dump and call the OpenAI API.
- "GPT 5.4 mini/nano" in the assignment PDF is not a real model id; `gpt-4o-mini` is used
  as the closest available mini-tier OpenAI model, configurable via `OPENAI_MODEL`.
- The assignment-supplied OpenAI key returns `401 invalid_api_key` regardless of model
  requested (verified directly against `/v1/models` and `/v1/chat/completions`), so it
  could not be used to verify live LLM calls in this environment - see
  `docs/design.md#known-limitations--tradeoffs-mvp1`.
- One customer per request (`customer_id` on `AgentRequest`); no multi-turn memory beyond
  what's in `conversation_id` - each request is handled statelessly. Multi-turn context
  is out of scope for MVP1.
- `streaming_available` seed data is a simple deterministic rule (every 3rd `film_id`,
  plus anything titled "Alien%") purely so the catalog demo has a realistic mix; it isn't
  meant to reflect a real catalog.

## Testing approach

Unit tests avoid depending on a live Postgres or a live OpenAI key so the suite runs
anywhere:
- DB-backed tools are tested against a mocked `Session` (asserts row-mapping and
  `ToolError` behavior), not a real database.
- `search_kb`/`create_handoff_ticket` are tested directly since they have no external
  dependency.
- Guardrail checks and the `GuardrailAgent` review are pure-function tests.
- API tests override the `get_kernel` FastAPI dependency; the three safety-critical eval
  scenarios (prompt injection, sensitive mutation, missing customer_id) are exercised
  end-to-end through the real orchestrator because none of them require a live LLM call
  on the paths being tested.

Running the eval examples in `evals/evals.json` end-to-end against a live server (real
Postgres + real OpenAI key) is a manual verification step, documented in the README -
an automated runner is a deferred bonus signal.

## Known limitations

See `docs/design.md#known-limitations--tradeoffs-mvp1`.
