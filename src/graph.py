"""Supervisor orchestration graph.

The orchestrator (supervisor) delegates the research task to three worker
sub-agents and compiles the final briefing. Built with ``langgraph-supervisor``
following the LangGraph "agent supervisor" pattern.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterator

from langchain_core.messages import HumanMessage

from . import prompts
from .agents import build_all_workers
from .llm import supervisor_llm


@lru_cache(maxsize=1)
def build_pipeline():
    """Build and compile the supervisor graph (cached for reuse)."""
    from langgraph_supervisor import create_supervisor

    workers = build_all_workers()
    supervisor = create_supervisor(
        agents=workers,
        model=supervisor_llm(),
        prompt=prompts.SUPERVISOR_PROMPT,
        # Prefix worker outputs so their provenance is preserved in the history.
        output_mode="last_message",
    )
    return supervisor.compile()


def _describe_step(node_name: str, node_state: dict[str, Any]) -> dict[str, Any] | None:
    """Turn a raw LangGraph update into a compact UI event."""
    messages = node_state.get("messages") if isinstance(node_state, dict) else None
    if not messages:
        return None
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, list):  # Gemini can return content parts
        content = " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    tool_calls = getattr(last, "tool_calls", None) or []
    names = [tc.get("name") for tc in tool_calls if isinstance(tc, dict) and tc.get("name")]
    # langgraph-supervisor delegates via synthetic "transfer_to_<agent>" tools.
    handoffs = [n[len("transfer_to_"):] for n in names if n.startswith("transfer_to_")]
    tools = [n for n in names if not n.startswith("transfer_to_")]
    return {
        "agent": node_name,
        "text": (content or "").strip(),
        "tools": tools,
        "handoffs": handoffs,
    }


def stream_events(question: str) -> Iterator[dict[str, Any]]:
    """Run the pipeline, yielding one event per agent step.

    Each event: {"agent": <node>, "text": <message>, "tools": [tool names]}.
    A terminal event has ``agent == "final"`` with the compiled briefing.
    """
    graph = build_pipeline()
    initial = {"messages": [HumanMessage(content=question)]}
    last_text = ""

    for update in graph.stream(initial, stream_mode="updates"):
        # ``updates`` yields {node_name: node_state} per step.
        for node_name, node_state in update.items():
            event = _describe_step(node_name, node_state)
            if event and event["text"]:
                last_text = event["text"]
            if event:
                yield event

    yield {"agent": "final", "text": last_text, "tools": [], "handoffs": []}


def run(question: str) -> str:
    """Synchronous convenience wrapper returning only the final briefing."""
    final = ""
    for event in stream_events(question):
        if event["agent"] == "final":
            final = event["text"]
    return final
