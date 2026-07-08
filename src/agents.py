"""Worker sub-agents, each a small ReAct agent with its own tools + prompt."""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from . import prompts, tools
from .llm import worker_llm


def build_web_search_agent():
    """ReAct agent that searches the web via Tavily.

    Falls back to a no-tool agent that explains the missing key if Tavily is
    not configured, so the graph still compiles and runs.
    """
    tavily = tools.build_tavily_tool()
    if tavily is None:
        prompt = (
            prompts.WEB_SEARCH_PROMPT
            + "\n\nNOTE: No TAVILY_API_KEY is configured, so web search is "
            "unavailable. Reply that external web search could not be performed."
        )
        agent_tools = []
    else:
        prompt = prompts.WEB_SEARCH_PROMPT
        agent_tools = [tavily]

    return create_react_agent(
        worker_llm(),
        tools=agent_tools,
        prompt=prompt,
        name="web_search_agent",
    )


def build_doc_summary_agent():
    """ReAct agent that reads and summarises internal documents."""
    return create_react_agent(
        worker_llm(),
        tools=[tools.list_documents, tools.read_document],
        prompt=prompts.DOC_SUMMARY_PROMPT,
        name="doc_summary_agent",
    )


def build_citation_validator_agent():
    """ReAct agent that validates citations / source URLs."""
    return create_react_agent(
        worker_llm(),
        tools=[tools.validate_url, tools.fetch_url_excerpt],
        prompt=prompts.CITATION_VALIDATOR_PROMPT,
        name="citation_validator_agent",
    )


def build_all_workers():
    return [
        build_doc_summary_agent(),
        build_web_search_agent(),
        build_citation_validator_agent(),
    ]
