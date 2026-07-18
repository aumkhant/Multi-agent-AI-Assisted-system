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

If your network intercepts HTTPS traffic and Python reports a certificate verification
error while calling `search_web`, set `WEB_SEARCH_CA_BUNDLE` in `.env` to your trusted
CA bundle. On this macOS setup, `/etc/ssl/cert.pem` is the system bundle.

### 4. Run migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

This adds `film.streaming_available` and creates `streaming_subscription` (seeded with
an active `Premium` subscription for `customer_id=1`, a cancelled `Basic`
subscription for `customer_id=2`, and a `Standard` trial subscription for
`customer_id=3`).

### 5. Run the app

```bash
uvicorn app.main:app --reload
```

```bash
curl -X POST localhost:8000/agent/respond \
  -H "Content-Type: application/json" \
  -d '{"customer_id": 1, "conversation_id": "conv_001", "message": "Is Alien available for streaming?"}'
```

### 6. (Optional) Run the local MCP server

The same tools used by the agents (`app/tools/`) are also exposed over a local MCP
server (`app/mcp_server.py`), so any MCP client (Claude Desktop, Claude Code, etc.) can
call `search_film_catalog`, `get_customer_streaming_subscription`,
`get_customer_rental_history`, `search_kb`, and `create_handoff_ticket` directly:

```bash
python -m app.mcp_server
```

This runs over stdio. To register it with Claude Code, add to `.mcp.json`:

```json
{
  "mcpServers": {
    "support-assistant-tools": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/absolute/path/to/this/repo"
    }
  }
}
```

### 7. Run tests

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
app/            FastAPI app, config, DB session, orchestrator, agents, tools, guardrails,
                mcp_server.py (local MCP server exposing the same tools)
alembic/        Migrations (0001 streaming_available column, 0002 streaming_subscription)
knowledge_base/ Local markdown articles used by search_kb
evals/          11 eval examples (input, expected intent/agent/tools, safety behavior)
tests/          Tool, guardrail, and API tests
docs/           design.md, implementation_plan.md, ai_usage.md
scripts/        restore_pagila.sh
```

## Agents

### Web Search Agent

**Purpose:** The Web Search Agent handles queries by searching the public web and synthesizing results into answers. It uses the `search_web` tool to retrieve real-time information from the internet, then leverages an LLM to answer the user's question based on those results while mentioning the most relevant source.

**When Invoked:** The Web Search Agent is currently available as a specialized agent (`app/agents/web_search_agent.py`) that can be called when extended functionality is needed. In the current triage flow, out-of-scope requests are handled by the GuardrailAgent, which politely redirects users to supported topics.

**Implementation Details:**

1. **Agent Handler** (`app/agents/web_search_agent.py`):
   - Accepts a user message and conversation ID
   - Calls the MCP client to execute the `search_web` tool
   - Processes search results through an LLM prompt that synthesizes information
   - Returns structured output with the answer, tools used, citations (URLs), and confidence metadata

2. **MCP Client Integration** (`app/mcp_client.py`):
   - The Web Search Agent uses `call_tool()` from the MCP client module to invoke tools
   - `call_tool(tool_name, conversation_id, arguments, output_model)` abstracts tool invocation:
     - `tool_name`: The tool to call (e.g., `"search_web"`)
     - `conversation_id`: Tracks the conversation context
     - `arguments`: A dictionary of tool parameters (e.g., `{"query": "..."}`)
     - `output_model`: The Pydantic schema for response validation
   - The MCP client dispatches the request to `dispatch_tool_call()` in `app/mcp_tools.py`

3. **Tool Dispatch Flow** (`app/mcp_tools.py`):
   - `dispatch_tool_call()` routes the tool name to the appropriate handler function
   - For `search_web`, it calls `app/tools/web_search.py::search_web()`
   - The tool executes the public web search (via DuckDuckGo instant answer API + HTML fallback)
   - Returns structured results with title, snippet, and source URL for each match

4. **Result Processing**:
   - If search results are empty, the agent returns a graceful "couldn't find a reliable answer" response
   - If results exist, they are passed to an LLM with a system prompt that ensures answers are grounded in the search results
   - The final response includes citations (URLs) to support transparency and traceability

**Example Flow:**
```
User Query → Web Search Agent → MCP Client (call_tool)
  → dispatch_tool_call() → search_web() tool
  → DuckDuckGo + HTML search results
  → MCP Client returns SearchWebOutput
  → LLM synthesizes answer from results
  → AgentOutcome with answer + citations
```

**Tool Metadata** (`app/tools/web_search.py`):
- **Name:** `search_web`
- **Input:** `SearchWebInput` (contains a `query: str` field)
- **Output:** `SearchWebOutput` (contains a `results: list[WebSearchResult]` with title, snippet, url)
- **Backed by:** DuckDuckGo instant answer API with HTML search results fallback
- **Auth:** None (public web search only)
