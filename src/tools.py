"""Tools used by the research sub-agents.

Grouped by the agent that owns them:
  * web-search agent      -> ``tavily_search``
  * document-summary agent -> ``list_documents`` / ``read_document``
  * citation-validator agent -> ``validate_url`` / ``check_source_supports_claim``
"""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from langchain_core.tools import tool

from .config import settings

_USER_AGENT = "Mozilla/5.0 (compatible; ResearchPipeline/0.1; +https://example.com/bot)"


# --------------------------------------------------------------------------- #
# Web search (Tavily)
# --------------------------------------------------------------------------- #
def build_tavily_tool():
    """Return the Tavily search tool, or ``None`` if no API key is configured.

    Kept as a factory (not a module-level object) so the app can start and show
    a helpful message when ``TAVILY_API_KEY`` is missing instead of crashing on
    import.
    """
    if not settings.has_tavily:
        return None
    from langchain_tavily import TavilySearch

    return TavilySearch(
        max_results=5,
        topic="general",
        include_answer=True,
        tavily_api_key=settings.tavily_api_key,
    )


# --------------------------------------------------------------------------- #
# Document access (internal knowledge base)
# --------------------------------------------------------------------------- #
_ALLOWED_SUFFIXES = {".txt", ".md", ".markdown", ".rst", ".csv", ".json"}


def _safe_doc_path(filename: str) -> Path:
    """Resolve ``filename`` inside DOCS_DIR, blocking path traversal."""
    base = settings.docs_dir.resolve()
    candidate = (base / filename).resolve()
    if base not in candidate.parents and candidate != base:
        raise ValueError(f"'{filename}' is outside the documents directory.")
    return candidate


@tool
def list_documents() -> str:
    """List the internal documents available for summarisation.

    Returns one filename per line. Call this first to discover what is in the
    knowledge base before reading a specific document.
    """
    base = settings.docs_dir
    if not base.exists():
        return f"No documents directory found at '{base}'."
    files = sorted(
        p.name
        for p in base.rglob("*")
        if p.is_file() and p.suffix.lower() in _ALLOWED_SUFFIXES
    )
    if not files:
        return f"The documents directory '{base}' is empty."
    return "Available documents:\n" + "\n".join(f"- {f}" for f in files)


@tool
def read_document(filename: str) -> str:
    """Read the full text of one internal document by filename.

    Args:
        filename: A name returned by ``list_documents`` (e.g. ``brief.md``).
    """
    try:
        path = _safe_doc_path(filename)
    except ValueError as exc:
        return f"Error: {exc}"
    if not path.exists() or not path.is_file():
        return f"Error: document '{filename}' was not found."
    if path.suffix.lower() not in _ALLOWED_SUFFIXES:
        return f"Error: '{filename}' is not a supported text document."
    text = path.read_text(encoding="utf-8", errors="replace")
    # Guard against pathological inputs blowing up the context window.
    if len(text) > 20_000:
        text = text[:20_000] + "\n\n...[truncated]"
    return f"# {filename}\n\n{text}"


# --------------------------------------------------------------------------- #
# Citation validation
# --------------------------------------------------------------------------- #
@tool
def validate_url(url: str) -> str:
    """Check whether a cited URL is well-formed and currently reachable.

    Performs a lightweight HTTP request and reports the status code so the
    citation-validator agent can flag dead or invalid sources.

    Args:
        url: The full source URL to verify (must start with http:// or https://).
    """
    if not url.lower().startswith(("http://", "https://")):
        return f"INVALID: '{url}' is not an http(s) URL."
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.getcode()
            final = resp.geturl()
        note = "" if final == url else f" (redirected to {final})"
        return f"REACHABLE: {url} returned HTTP {code}{note}."
    except urllib.error.HTTPError as exc:
        verdict = "REACHABLE" if exc.code < 500 else "UNREACHABLE"
        return f"{verdict}: {url} returned HTTP {exc.code} ({exc.reason})."
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return f"UNREACHABLE: {url} could not be fetched ({exc})."


@tool
def fetch_url_excerpt(url: str, max_chars: int = 2000) -> str:
    """Fetch a short plain-text excerpt of a page to confirm it supports a claim.

    Strips HTML tags crudely and returns the leading text. Use this to check
    that a source actually mentions the fact it is cited for.

    Args:
        url: The source URL to fetch.
        max_chars: Maximum number of characters to return (default 2000).
    """
    if not url.lower().startswith(("http://", "https://")):
        return f"INVALID: '{url}' is not an http(s) URL."
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(200_000).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - report any fetch failure to the agent
        return f"UNREACHABLE: could not fetch {url} ({exc})."

    import re

    # Drop scripts/styles then all remaining tags, then collapse whitespace.
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    clamped = max(200, min(max_chars, 8000))
    return text[:clamped] if text else "(no readable text extracted)"
