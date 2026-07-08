"""Gemini chat-model factory.

A single place to build ``ChatGoogleGenerativeAI`` instances so every agent
shares the same provider configuration. Import is deferred inside the factory
so the module can be imported (e.g. for tests) even if the optional dependency
is missing.
"""
from __future__ import annotations

from functools import lru_cache

from .config import settings


@lru_cache(maxsize=8)
def build_llm(model: str, temperature: float | None = None):
    """Return a cached Gemini chat model bound to the given name."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if not settings.has_google:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Copy .env.example to .env and add your "
            "Gemini API key (https://aistudio.google.com/app/apikey)."
        )

    return ChatGoogleGenerativeAI(
        model=model,
        temperature=settings.temperature if temperature is None else temperature,
        google_api_key=settings.google_api_key,
        # Gemini occasionally returns empty parts; retry keeps the graph robust.
        max_retries=3,
    )


def supervisor_llm():
    return build_llm(settings.supervisor_model)


def worker_llm():
    return build_llm(settings.worker_model)
