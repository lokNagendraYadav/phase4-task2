"""CLI entry point for the multi-agent research pipeline.

Usage:
    python run.py "Research Acme Corp: funding, products and recent news"
    python run.py            # prompts interactively
"""
from __future__ import annotations

import sys

from src.config import settings
from src.graph import stream_events

_LABELS = {
    "supervisor": "🧭 Orchestrator",
    "web_search_agent": "🌐 Web Search",
    "doc_summary_agent": "📄 Doc Summary",
    "citation_validator_agent": "✅ Citation Validator",
    "final": "📌 FINAL BRIEFING",
    "error": "❌ Error",
}


def main() -> int:
    if not settings.has_google:
        print("GOOGLE_API_KEY is not set. Copy .env.example to .env first.", file=sys.stderr)
        return 1

    question = " ".join(sys.argv[1:]).strip()
    if not question:
        question = input("Research question> ").strip()
    if not question:
        print("No question provided.", file=sys.stderr)
        return 1

    if not settings.has_tavily:
        print("(warning: TAVILY_API_KEY not set — web search will be skipped)\n")

    for event in stream_events(question):
        label = _LABELS.get(event["agent"], event["agent"])
        print(f"\n{'=' * 70}\n{label}\n{'-' * 70}")
        if event["tools"]:
            print(f"[tools: {', '.join(event['tools'])}]")
        print(event["text"] or "(working…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
