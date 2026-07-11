# AI tool usage

## Tool used

Claude Code (Anthropic), used interactively for this entire take-home.

## What it helped with

- Reading and extracting the requirements from the assignment PDF (`pdftotext`, since
  the PDF wasn't machine-readable via the file preview alone).
- Scaffolding the whole project: `app/` package layout, Alembic setup, Docker Compose
  for Postgres, tool contracts, Semantic Kernel agent wiring, the orchestrator, FastAPI
  endpoint, guardrail checks, tests, evals, and this docs folder.
- Proposing the MVP1 scope cut (full required functional slice, bonus signals like an
  MCP server / tracing / streaming deferred) and the deterministic-tool-call-then-LLM-
  phrasing pattern for specialist agents, both of which were confirmed with the human
  developer before implementation started.

## What was manually reviewed / decided by the human developer

- The choice of LLM provider/model (using the assignment-supplied OpenAI key with a
  mini-tier model, rather than a different provider) and the overall MVP1 scope boundary
  were explicit decisions made by the developer in response to Claude's clarifying
  questions, not autonomous choices.
- The routing/guardrail flow was refined through human review after implementation.
  In particular, the developer explicitly challenged the initial behavior for unrelated
  queries, which led to adding an `out_of_scope` path in triage plus deterministic
  detection for clearly unrelated requests before they could fall through to the
  knowledge-base agent.
- The developer also explicitly validated that high-priority safety checks such as
  `is_harmful_content_request` belong before the triage LLM call in the orchestrator,
  so those categories are blocked deterministically rather than depending on model
  classification.
- The code structure was refactored based on developer direction to make module
  boundaries cleaner: the Pydantic request/response models that were originally spread
  across the tool files were centralized into `app/schemas.py`, while the tool modules
  were narrowed to their operational responsibilities only (database access, local
  knowledge-base lookup, or mock handoff ticket creation).
- All generated code was reviewed for correctness against the assignment's literal
  requirements (response schema fields, required agents/tools, migration shape, safety
  test cases) before being accepted; the test suite (19 tests) was run and confirmed
  passing as part of that review, not just generated and left unverified.
- Design tradeoffs called out in `docs/design.md` (deterministic vs. LLM-driven tool
  selection, rule-based vs. LLM-based guardrail review) were reasoned through and
  accepted deliberately, with the reasoning captured in that document so it can be
  challenged/revisited rather than taken on faith.
- The exposed API key in the assignment PDF was kept out of version control - only
  `.env.example` with a placeholder is committed; the real key is expected to be placed
  in a local, gitignored `.env`.
