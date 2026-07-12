# Design

## Architecture overview

```
POST /agent/respond
        │
        ▼
Deterministic input guardrails (prompt injection / harmful content / sensitive mutation)
        │  (only if the message passes)
        ▼
TriageAgent  (LLM classification -> intent, selected_agent, confidence, reason)
        │  (low confidence -> HumanHandoffAgent fallback)
        │  (explicit unrelated-topic detection -> GuardrailAgent / out_of_scope)
        ▼
Specialist agent (Catalog | Subscription | RentalHistory | Knowledge | HumanHandoff)
        │  each specialist calls exactly its own tool(s), then an LLM call
        │  phrases the answer grounded in the tool's typed output
        ▼
GuardrailAgent  (final review: schema, leaked-prompt check, ungrounded-claim check, length)
        │
        ▼
AgentResponse (structured JSON)
```

FastAPI owns the HTTP surface; `app/orchestrator.py` is the only place that sequences
agents. Every agent module exposes a plain function (`handle`/`classify`/`review`) rather
than a class hierarchy - there's one router (Triage), one safety net (Guardrail), and a
handful of narrowly-scoped specialists, so a shared base class would add indirection
without buying anything at this size.

LLM access is intentionally funneled through `app/utils/llm.py`, which wraps Semantic
Kernel around an OpenAI-compatible chat interface. That keeps the agent code provider-
agnostic and allows the same orchestration flow to run either against a hosted OpenAI
model or a local Ollama model exposed through its OpenAI-compatible `/v1` endpoint.

## Why deterministic guardrails run before triage

Prompt injection ("ignore previous instructions...") and sensitive account mutation
("cancel my subscription now"), plus clearly harmful-content requests, are safety-critical
failure modes explicitly called
out in the assignment's eval table. Relying on the LLM to refuse them is not robust - a
mini model can be talked out of a soft instruction. Both cases are instead caught by
regex checks in `app/guardrails/checks.py` *before* the LLM triage call ever runs, so
the safe behavior does not depend on the model's judgement on that turn:

- Prompt injection -> blocked immediately, `GuardrailAgent`/`unsafe_request`, no LLM call.
- Harmful content -> blocked immediately, `GuardrailAgent`/`unsafe_request`, no LLM call.
- Sensitive mutation -> escalated immediately to `HumanHandoffAgent`, which creates a
  ticket and explicitly states no account change was made.

There is also a lightweight deterministic out-of-scope detector in triage for obviously
unrelated requests (for example sports/news/weather/medical/coding questions). That path
avoids wasting a knowledge-base lookup on clearly off-domain traffic while still keeping
the main routing decision inside the single triage step rather than adding a second LLM
call just for scope detection.

An earlier revision also gated any in-scope LLM classification on matching a fixed
domain-keyword list (`_DOMAIN_RE`) before trusting it, downgrading to `out_of_scope`
otherwise. That was removed: it produced false positives on legitimate requests that
don't happen to contain a domain keyword (e.g. "Do you have Amadeus Holy?" - a pure
title lookup with no word like "movie"/"stream" in it). The gate isn't needed for
correctness anyway, because every specialist agent (Catalog/Subscription/RentalHistory/
Knowledge) only answers from its tool's JSON output and explicitly handles the
no-match/empty case (e.g. CatalogAgent says the film could not be found), so a
misrouted off-topic message can't produce a hallucinated answer even without this gate.

The `GuardrailAgent` still runs a second, LLM-output-side pass (`app/agents/guardrail_agent.py`)
after any specialist responds, checking for leaked system-prompt phrasing and for
"grounded" intents (catalog/subscription/rental/knowledge) that somehow produced an
answer without calling a tool - a defensive check against future regressions, not just
a redundant one.

## Agents

| Agent | Responsibility | Tools |
|---|---|---|
| TriageAgent | Classify intent, pick specialist, emit confidence + reason. Falls back to deterministic keyword/out-of-scope rules if the LLM call fails or returns unparsable JSON. | none |
| CatalogAgent | Film/streaming questions | `search_film_catalog` |
| SubscriptionAgent | Subscription status/renewal | `get_customer_streaming_subscription` |
| RentalHistoryAgent | Recent rental summary | `get_customer_rental_history` |
| KnowledgeAgent | General support Q&A | `search_kb` |
| HumanHandoffAgent | Escalation, risky requests, low-confidence fallback | `create_handoff_ticket` |
| GuardrailAgent | Final answer review | none (deterministic checks only) |

Each specialist calls its tool **deterministically** (the agent code invokes the tool
directly, not via LLM function-calling) and then makes a single LLM call to phrase the
final answer, instructed to use only the tool's JSON output. This trades away
"the model decides when to call a tool" flexibility for something more important at
this scope: every tool call is guaranteed to happen exactly when routing says it should,
tool inputs/outputs stay strictly typed, and the behavior is testable without needing a
live model to exercise the function-calling loop correctly. `search_film_catalog` and
`get_customer_streaming_subscription`/`get_customer_rental_history` are still exposed
with full MCP-ready metadata (see below), so swapping in real LLM-driven tool selection
later is a contained change, not a rewrite.

## Tool contracts and MCP readiness

Every tool (`app/tools/*.py`) has:
- A typed Pydantic input model and output model, centralized in `app/schemas.py`.
- A `ToolMetadata` record (name, description, input/output JSON schema, error behavior,
  auth requirement, ownership boundary, backing system) - this is the MCP-ready contract
  the assignment asks for, without standing up an actual MCP server for MVP1.
- A `logged_tool_call` context manager that logs conversation_id, tool name, status,
  latency, and error detail for every invocation.

`search_film_catalog`, `get_customer_streaming_subscription`, and
`get_customer_rental_history` are backed by Postgres/Pagila via SQLAlchemy Core
(parameterized `text()` queries - no string-built SQL). `search_kb` reads local markdown
files under `knowledge_base/`. `create_handoff_ticket` writes to an in-memory list (mock,
per the assignment's "Mock" designation).

A local MCP server (`app/mcp_server.py`, run via `python -m app.mcp_server`) now exposes
all five tools over stdio using `mcp.server.fastmcp.FastMCP`, reusing the same
`app/tools/*.py` functions and `ToolMetadata` name/description - so an MCP client
(Claude Desktop, Claude Code, etc.) can call `search_film_catalog`,
`get_customer_streaming_subscription`, `get_customer_rental_history`, `search_kb`, and
`create_handoff_ticket` directly, independent of the FastAPI orchestrator. See the
README for how to register it with an MCP client.

## Database

Migrations 0001/0002 (Alembic) add `film.streaming_available` and create
`streaming_subscription`, matching the assignment's schema spec exactly. Migration 0001
also seeds a plausible mix of `streaming_available` values (every third film, plus
anything titled "Alien%") so the catalog demo has realistic mixed results out of the
box; migration 0002 seeds three subscription rows for local testing: an active Premium
subscription for `customer_id=1`, a cancelled Basic subscription for `customer_id=2`,
and a Standard trial subscription for `customer_id=3`.

## Guardrails and safety

- **Never reveal system instructions.** Deterministic regex check + a second check on
  the final answer text.
- **Never assist with harmful-content requests.** These are blocked before triage using a
  deterministic regex check so refusal is not dependent on LLM behavior.
- **Never mutate account state.** No tool exists that can change a subscription/account;
  `create_handoff_ticket` only ever creates a ticket. Sensitive-sounding requests are
  intercepted before triage and always routed to `HumanHandoffAgent`.
- **Stay in domain.** Obviously unrelated questions are routed to `out_of_scope` and
  answered with a domain-limitation message instead of hitting the support KB.
- **Protect customer data.** Specialist agents only ever query by the `customer_id` on
  the current request; there is no tool that takes an arbitrary customer_id from
  message text.
- **Missing customer_id.** Subscription/RentalHistory agents check for `None` and return
  a clear "I need your customer ID" answer with `next_action=await_customer_id` instead
  of crashing or querying with a null value.

## Structured response contract

`AgentResponse` (Pydantic, `app/schemas.py`) enforces the exact required fields
(`conversation_id, intent, selected_agent, answer, confidence, tools_used, citations,
next_action, guardrail_result`) with closed `Literal` types for the enum-like fields, so
a malformed value from any agent fails fast as a validation error rather than reaching
the client.

## Observability

Tool calls and guardrail interventions are logged as structured log records (Python
`logging`, `extra={...}`) rather than plain strings, so they're greppable/parseable.
Wiring this to a real log sink (JSON file, OpenTelemetry, Langfuse) is a deferred bonus
signal, not core MVP1 scope.

## Known limitations / tradeoffs (MVP1)

- Tool selection is deterministic per-agent, not LLM function-calling - see above for why.
- `search_film_catalog` uses `ILIKE` substring search with a simple stopword-based query
  extractor (`app/utils/query_extraction.py`); it is not semantic search and can miss
  titles phrased very differently from the message.
- GuardrailAgent's final review is rule-based, not an additional LLM call - keeps the
  request path to at most 2 LLM calls (triage + one specialist) and avoids a third,
  harder-to-test LLM-judged step. An LLM-based review pass is a natural next iteration.
- No streaming responses, no tracing/cost logging, no Docker Compose for the app itself
  (only for Postgres) - these are the assignment's explicitly-labeled bonus signals,
  deferred out of MVP1 by design. (A local MCP server is now implemented - see
  "Tool contracts and MCP readiness" above.)
- Eval examples are provided as data (`evals/evals.json`, currently 11 scenarios); an
  automated eval-runner script is a bonus signal, not yet implemented.
