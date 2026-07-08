# Multi-Agent Research Pipeline

An **orchestrator agent that delegates to specialist sub-agents** — web search,
document summary, and citation validation — coordinated with **LangGraph** and
powered by **Google Gemini**. Comes with a FastAPI web UI that streams each
agent step live, plus a CLI.

Use cases: **client research automation** and **internal knowledge retrieval**.

---

## Architecture

```
                    ┌──────────────────────────────┐
   user question ──▶│   Orchestrator (Supervisor)   │◀── writes final briefing
                    │   gemini-2.0-flash            │
                    └──────────────┬───────────────┘
                     delegates one │ agent at a time
        ┌────────────────────────┼────────────────────────────┐
        ▼                        ▼                              ▼
┌────────────────┐    ┌────────────────────┐    ┌──────────────────────────┐
│ web_search     │    │ doc_summary        │    │ citation_validator       │
│ • Tavily search│    │ • list_documents   │    │ • validate_url           │
│                │    │ • read_document    │    │ • fetch_url_excerpt      │
└────────────────┘    └────────────────────┘    └──────────────────────────┘
   public web            internal docs/            checks every cited URL is
   (with source URLs)    knowledge base            reachable & supports claim
```

The supervisor pattern follows the LangGraph
[agent-supervisor tutorial](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/).
Each worker is a `create_react_agent` with its own tools and system prompt; the
supervisor (`langgraph-supervisor.create_supervisor`) routes control between
them and produces the final report.

## Project layout

```
phase4-task2/
├── run.py                 # CLI entry point
├── requirements.txt
├── .env.example           # copy to .env and fill in keys
├── docs/                  # sample internal knowledge base
│   ├── project_atlas_brief.md
│   └── client_acme_notes.md
└── src/
    ├── config.py          # env / settings
    ├── llm.py             # Gemini chat-model factory
    ├── tools.py           # Tavily search, doc reader, URL validator
    ├── prompts.py         # supervisor + worker system prompts
    ├── agents.py          # the three ReAct sub-agents
    ├── graph.py           # supervisor graph + event streaming
    └── app.py             # FastAPI web UI (SSE streaming)
```

## Setup

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. configure keys
cp .env.example .env        # Windows: copy .env.example .env
#   GOOGLE_API_KEY  -> https://aistudio.google.com/app/apikey
#   TAVILY_API_KEY  -> https://app.tavily.com/   (free tier)
```

> Without `TAVILY_API_KEY` the pipeline still runs — the web-search agent simply
> reports that external search is unavailable, and the rest of the graph works.

## Run

**Web UI** (recommended — watch the orchestrator delegate in real time):

```bash
uvicorn src.app:app --reload
# open http://127.0.0.1:8000
```

**CLI:**

```bash
python run.py "Research Anthropic: products, funding and leadership; cross-check with our internal notes"
```

Health check: `GET /health` reports whether each API key is configured.

## How it works

1. **Orchestrator** receives the request and delegates to `doc_summary_agent`
   to ground the work in internal knowledge.
2. It then delegates to `web_search_agent` to gather current public facts, each
   with a source URL.
3. The combined draft goes to `citation_validator_agent`, which verifies every
   cited URL is reachable and actually supports the claim
   (✅ VERIFIED / ⚠️ WEAK / ❌ UNSUPPORTED).
4. If claims are flagged, the orchestrator routes back for fixes, then writes a
   final briefing: **Summary · Key Findings · Internal Notes · Citation Check ·
   Open Questions**.

## Configuration

| Variable           | Default            | Purpose                              |
|--------------------|--------------------|--------------------------------------|
| `GOOGLE_API_KEY`   | —                  | Gemini API key (required)            |
| `TAVILY_API_KEY`   | —                  | Web search (optional)                |
| `SUPERVISOR_MODEL` | `gemini-2.0-flash` | Orchestrator model                   |
| `WORKER_MODEL`     | `gemini-2.0-flash` | Sub-agent model                      |
| `LLM_TEMPERATURE`  | `0.1`              | Sampling temperature                 |
| `DOCS_DIR`         | `docs`             | Internal knowledge-base directory    |

Drop your own `.txt` / `.md` / `.csv` / `.json` files into `docs/` to research
against your own internal knowledge base.
