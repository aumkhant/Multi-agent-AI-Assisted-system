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
5. **Mock tools** - `search_kb` over `knowledge_base/*.md`; `handoff_ticket` resource with
   full CRUD operations (`create_handoff_ticket`, `get_handoff_ticket`,
   `list_handoff_tickets`, `update_handoff_ticket`, `delete_handoff_ticket`) implemented
   as an in-memory store. Read-only tools (`search_film_catalog`,
   `get_customer_streaming_subscription`, `get_customer_rental_history`, `search_kb`,
   `search_web`) are intentionally designed without mutation operations to preserve
   safety and ownership boundaries.
6. **Agents + observability** - Semantic Kernel `Kernel` + `OpenAIChatCompletion`
   service (`app/utils/llm.py`), one module per agent. Triage does LLM JSON
   classification with a deterministic keyword fallback. Specialists call their tools
   through the MCP client (`app/mcp_client.py::call_tool()`) rather than importing tool
   functions directly, ensuring all tool invocations go through the standardized MCP
   dispatch layer. After tool execution, one LLM call phrases the answer from the
   tool's typed JSON output. OpenTelemetry spans wrap the completion path and attach
   model/temperature/token-usage metadata so latency and usage can be inspected during
   development and later exported to a collector.
7. **Guardrails** - deterministic input-side checks (`app/guardrails/checks.py`) run
   before triage; a rule-based `GuardrailAgent` review runs after the specialist answers.
8. **Orchestrator + API** - `app/orchestrator.py` sequences the above;
   `POST /agent/respond` in `app/main.py` returns the validated `AgentResponse`.
9. **Tests** - tool tests (mocked DB session + real KB/handoff mock stores), guardrail
   tests (pure functions), API tests (FastAPI `TestClient`, kernel dependency overridden
   so tests don't need a live OpenAI key; safety-critical paths are exercised
   end-to-end since they don't require the LLM).
10. **Evals** - `evals/evals.json`, 14 examples covering every required eval-table row
    plus web search fallback scenarios (KB search miss, catalog miss, product-adjacent
    queries), and extra edge cases.
11. **Docs** - this plan, `docs/design.md`, `docs/ai_usage.md`, README setup steps.

## Key architectural decisions

### 1. Agents invoke tools through MCP client, not direct imports

All specialist agents (`CatalogAgent`, `SubscriptionAgent`, `RentalHistoryAgent`,
`KnowledgeAgent`, `WebSearchAgent`) invoke their tools via `app/mcp_client.py::call_tool()`
rather than importing and calling the tool functions directly. This ensures:
- Unified tool dispatch path aligned with MCP contracts (`app/mcp_tools.py`)
- Centralized logging and lifecycle management
- Testability: tool calls can be mocked at the dispatch layer
- Future extensibility: local MCP server (`app/mcp_server.py`) and in-app agents share
  the same registry and contracts

### 2. Full CRUD coverage for operational resources

Only the `handoff_ticket` resource (owned and managed by the assistant) has full CRUD
operations: `create_handoff_ticket`, `get_handoff_ticket`, `list_handoff_tickets`,
`update_handoff_ticket`, `delete_handoff_ticket`. All other tools are intentionally
read-only (`search_film_catalog`, `get_customer_streaming_subscription`,
`get_customer_rental_history`, `search_kb`, `search_web`) because they represent either
source-of-truth external systems (catalog, subscriptions, customer account data) or
curated content (knowledge base). This preserves safety and ownership boundaries while
meeting the CRUD requirement.

### 3. Unanswered queries fall back to web search

If a specialist agent cannot answer a query from its first-party data source (e.g., a
film title is not in the catalog, no relevant KB article exists), the orchestrator
replaces the specialist's response with `WebSearchAgent`'s response. The response
retains the original `intent` for traceability but switches `selected_agent` to
`WebSearchAgent`. This ensures no unanswered questions and increases assistant utility
without hallucinating or making up product information.

### 4. Human handoff only for explicit requests, not as fallback

The `HumanHandoffAgent` is invoked only in two scenarios:
1. **Explicit user request**: Customer explicitly asks to speak with a human agent.
2. **Safety interception**: Deterministic guardrails (sensitive account mutation) force
   escalation to preserve safety. In this case, a handoff ticket is created with an
   explanation, but no account mutation is performed.

The orchestrator no longer uses handoff as a confidence-based fallback or fallback for
unclassified requests. This improves the assistant's resolution rate and reduces
unnecessary escalations.

## Checklist

- [x] Project scaffold, venv, dependencies install cleanly (`pip install -e ".[dev]"`)
- [x] Docker Compose Postgres + Pagila restore script
- [x] Alembic migrations 0001/0002 with seed data
- [x] `search_film_catalog`, `get_customer_streaming_subscription`,
      `get_customer_rental_history` (typed, MCP metadata, logged, read-only)
- [x] `search_kb`, `search_web` (typed, MCP metadata, logged, read-only)
- [x] `handoff_ticket` with full CRUD (typed, MCP metadata, logged)
- [x] TriageAgent, CatalogAgent, SubscriptionAgent, RentalHistoryAgent, KnowledgeAgent,
      HumanHandoffAgent, WebSearchAgent, GuardrailAgent
- [x] All specialist agents invoke tools through MCP client (`app/mcp_client.py::call_tool()`)
      rather than direct imports
- [x] Orchestrator implements web search fallback when specialist agents cannot answer
- [x] Orchestrator implements explicit-only handoff (no fallback escalation)
- [x] Orchestrator + `POST /agent/respond` returning the required structured JSON
- [x] Deterministic guardrails: prompt injection, sensitive mutation, missing customer_id
- [x] Tests: tools, guardrails, API, MCP server (24 tests, all passing without a live DB/LLM)
- [x] `evals/evals.json` with 14 examples
- [x] OpenTelemetry-based tracing for LLM operations with token-usage metadata
- [x] `docs/design.md`, `docs/implementation_plan.md`, `docs/ai_usage.md`, README

## Assumptions

- The grading environment can run Docker (for Postgres) and has outbound network access
  to fetch the Pagila dump; LLM calls can be satisfied either by the hosted OpenAI API or
  by a local Ollama model exposed through its OpenAI-compatible endpoint.
- The model id is configurable through `OPENAI_MODEL`, and provider selection is handled
  through `OPENAI_BASE_URL` in the shared LLM utility.
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
Postgres + a working hosted or local LLM endpoint) is a manual verification step, documented in the README -
an automated runner is a deferred bonus signal.

## Known limitations

See `docs/design.md#known-limitations--tradeoffs-mvp1`.
