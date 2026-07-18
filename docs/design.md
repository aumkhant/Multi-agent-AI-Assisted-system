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
        │  (explicit unrelated-topic detection -> GuardrailAgent / out_of_scope)
        ▼
Specialist agent (Catalog | Subscription | RentalHistory | Knowledge | HumanHandoff)
        │  each specialist calls its tool through MCP client (app/mcp_client.py)
        │  MCP dispatch ensures all tool calls go through standardized registry
        │  then an LLM call phrases the answer grounded in the tool's typed output
        │  (if unanswered -> WebSearchAgent fallback)
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

## Observability and tracing

The application now includes an OpenTelemetry-based observability layer for LLM and tool
execution. `app/utils/tracing.py` creates spans around the main completion path, and
`app/utils/llm.py` enriches those spans with metadata such as the model name,
temperature, and provider-reported token usage from the completion result.

This gives the project a lightweight, vendor-neutral tracing story without requiring a
full distributed tracing stack at MVP1. By default, spans are emitted to the console via
OpenTelemetry's console exporter, and the same pattern can later be extended to OTLP,
Jaeger, or other collectors.

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

**Human handoff is explicit-only**: The orchestrator no longer uses handoff as a
fallback for confidence-based routing or unclassified requests. `HumanHandoffAgent` is
invoked only when:
1. The customer explicitly asks to speak with a human.
2. Deterministic guardrails intercept sensitive account mutations to ensure safe escalation.

This improves resolution rate and prevents unnecessary human escalations, reserving 
handoff for genuinely appropriate scenarios.

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

## MCP-first agent architecture

### 1. Agents invoke tools through MCP client, not direct imports

Rather than importing tool functions directly (e.g., `from app.tools.catalog import
search_film_catalog`), all specialist agents call their tools via `app/mcp_client.py`:

```python
from app.mcp_client import call_tool

result = await call_tool(
    "search_web",              # Tool name
    conversation_id,           # Conversation context
    {"query": message},        # Arguments
    SearchWebOutput,           # Output schema for validation
)
```

This design ensures:
- **Unified dispatch**: All tool invocations go through `app/mcp_tools.py::dispatch_tool_call()`,
  which routes named tool calls to handlers.
- **Shared contracts**: Both in-app agents and the local MCP server (`app/mcp_server.py`)
  invoke the same tools with the same input/output schemas.
- **Testability**: Tool calls can be mocked at the dispatch layer, enabling agent testing
  without real tool execution.
- **Observability**: Logging and lifecycle management are centralized.

### 2. Full CRUD operations on owned resources only

The assistant owns and manages only one resource: `handoff_ticket`. This resource has
complete CRUD coverage:
- `create_handoff_ticket` - Create a new support ticket
- `get_handoff_ticket` - Retrieve ticket by ID
- `list_handoff_tickets` - List all tickets for a conversation
- `update_handoff_ticket` - Modify ticket status/notes
- `delete_handoff_ticket` - Remove a ticket

All other tools are intentionally read-only:
- `search_film_catalog` - Queries external catalog (Pagila schema)
- `get_customer_streaming_subscription` - Reads account data
- `get_customer_rental_history` - Reads rental records
- `search_kb` - Reads curated knowledge base articles
- `search_web` - Reads public web search results

Read-only tools preserve safety boundaries and ownership clarity. Forcing mutations onto
external systems (catalog, account data) or curated content (knowledge base) would either
violate guardrails or blur operational responsibilities. This design satisfies the CRUD
requirement while respecting trust and authorization boundaries.

### 3. Unanswered queries fall back to web search

When a specialist agent cannot answer from its source (empty search results, no matching
records, etc.), the orchestrator transparently replaces that response with
`WebSearchAgent`'s response:

```python
if not outcome.answered:
    outcome = await web_search_agent.handle(kernel, conversation_id, message)
    # outcome.selected_agent = "WebSearchAgent"
    # outcome.intent = original_triage_intent  # preserved for traceability
```

Benefits:
- **No unanswered questions**: Every query gets an attempt at resolution.
- **Grounded responses**: Web search results are real public data, not hallucinations.
- **Traceability**: Original intent is preserved while `selected_agent` indicates the
  fallback path taken.
- **Utility**: Assistant can answer product-adjacent questions ("Where can I watch X?"
  -> web search if not in catalog) without hallucinating internal data.

### 4. Human handoff is explicit-only, not a fallback

Previously, `HumanHandoffAgent` might have been invoked as a fallback for confidence-based
routing or unclassified requests. The new design reserves handoff for two explicit cases:

1. **Explicit user request**: "I want to speak to a human agent"
   - Triage detects intent = `human_handoff`
   - Orchestrator calls `HumanHandoffAgent`, which creates a ticket and informs the user
   
2. **Safety interception**: Sensitive mutation guardrails force escalation
   - Deterministic check in orchestrator detects sensitive request
   - Escalates to `HumanHandoffAgent` with reason = `sensitive_account_mutation_request`
   - Ticket is created with full context; no account change is performed

This improves the assistant's resolution rate by eliminating unnecessary escalations,
while ensuring truly problematic cases get appropriate human review.

## Agents

| Agent | Responsibility | Tools |
|---|---|---|
| TriageAgent | Classify intent, pick specialist, emit confidence + reason. Falls back to deterministic keyword/out-of-scope rules if the LLM call fails or returns unparsable JSON. | none |
| CatalogAgent | Film/streaming questions | `search_film_catalog` |
| SubscriptionAgent | Subscription status/renewal | `get_customer_streaming_subscription` |
| RentalHistoryAgent | Recent rental summary | `get_customer_rental_history` |
| KnowledgeAgent | General support Q&A | `search_kb` |
| HumanHandoffAgent | Escalation only for explicit user requests or sensitive-mutation guardrail interception | `create_handoff_ticket` |
| WebSearchAgent | Public-web fallback when a specialist cannot answer from first-party data | `search_web` |
| GuardrailAgent | Final answer review | none (deterministic checks only) |

Each specialist calls its tool **through the app's MCP tool surface** rather than
importing the underlying Python tool function directly. Concretely, `app/mcp_client.py`
dispatches named MCP-style tool calls, and both the agents and `app/mcp_server.py` share
the same registry in `app/mcp_tools.py`. This keeps the runtime path aligned with the
published MCP contracts while preserving deterministic tool usage and typed inputs/outputs.

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
files under `knowledge_base/`. `search_web` reads public web results from DuckDuckGo's
Instant Answer API. `handoff_ticket` is the only resource with full CRUD, implemented as
an in-memory store (`create_handoff_ticket`, `get_handoff_ticket`, `list_handoff_tickets`,
`update_handoff_ticket`, `delete_handoff_ticket`).

A local MCP server (`app/mcp_server.py`, run via `python -m app.mcp_server`) now exposes
all tools over stdio using `mcp.server.fastmcp.FastMCP`, reusing the same shared tool
registry that the agents call through. That means an MCP client (Claude Desktop, Claude
Code, etc.) and the in-app agents both hit the same named tool contracts.

Only `handoff_ticket` gets CRUD because it is the only operational resource this
assistant owns outright. The catalog, subscription, rental history, and knowledge-base
tools are intentionally read-only: they represent source-of-truth product/account data
or curated support content, so forcing artificial create/update/delete operations onto
them would either violate current safety boundaries (for account data) or blur the
difference between the assistant's runtime query path and a separate content-management
workflow. Keeping those tools read-only preserves the original ownership and guardrail
assumptions while still meeting the CRUD requirement on a resource that the app is
designed to manage directly.

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
- **Never mutate account state.** No tool exists that can change a subscription/account.
  Sensitive-sounding requests are intercepted before triage and routed to
  `HumanHandoffAgent`, which creates a handoff ticket but performs no account mutation.
- **Stay in domain.** Obviously unrelated questions are routed to `out_of_scope` and
  answered with a domain-limitation message instead of hitting the support KB.
- **Protect customer data.** Specialist agents only ever query by the `customer_id` on
  the current request; there is no tool that takes an arbitrary customer_id from
  message text.
- **Missing customer_id.** Subscription/RentalHistory agents check for `None` and return
  a clear "I need your customer ID" answer with `next_action=await_customer_id` instead
  of crashing or querying with a null value.
- **Human handoff is explicit-only, except safety interception.** The orchestrator no
  longer uses handoff as a confidence-based fallback. It is used only when the customer
  explicitly asks for a human, or when the sensitive-mutation guardrail forces safe
  escalation.
- **Unanswered specialist requests fall back to public web search.** If a specialist
  cannot answer from its first-party source, the orchestrator replaces that specialist
  outcome with `WebSearchAgent`'s response. The response's `selected_agent` is
  `WebSearchAgent`, while `intent` remains the original triaged intent for traceability.

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

- Tool selection is deterministic per-agent (agents invoke named tools through the MCP
  client rather than using LLM function-calling). This design is intentional, not a
  limitation - see "MCP-first agent architecture" above for why deterministic routing is
  preferred.
- `search_film_catalog` uses `ILIKE` substring search with a simple stopword-based query
  extractor (`app/utils/query_extraction.py`); it is not semantic search and can miss
  titles phrased very differently from the message.
- GuardrailAgent's final review is rule-based, not an additional LLM call - keeps the
  request path to at most 2 LLM calls (triage + one specialist) and avoids a third,
  harder-to-test LLM-judged step. An LLM-based review pass is a natural next iteration.
- No streaming responses, no tracing/cost logging, no Docker Compose for the app itself
  (only for Postgres) - these are the assignment's explicitly-labeled bonus signals,
  deferred out of MVP1 by design. A local MCP server is now implemented to expose tools
  over stdio.
- Eval examples are provided as data (`evals/evals.json`, currently 14 scenarios); an
  automated eval-runner script is a bonus signal, not yet implemented.
