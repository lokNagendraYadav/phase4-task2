"""Central configuration loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None
    tavily_api_key: str | None
    supervisor_model: str
    worker_model: str
    temperature: float
    docs_dir: Path

    @property
    def has_google(self) -> bool:
        return bool(self.google_api_key)

    @property
    def has_tavily(self) -> bool:
        return bool(self.tavily_api_key)


def _resolve_docs_dir(raw: str) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def load_settings() -> Settings:
    return Settings(
        google_api_key=os.getenv("GOOGLE_API_KEY") or None,
        tavily_api_key=os.getenv("TAVILY_API_KEY") or None,
        supervisor_model=os.getenv("SUPERVISOR_MODEL", "gemini-2.0-flash"),
        worker_model=os.getenv("WORKER_MODEL", "gemini-2.0-flash"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        docs_dir=_resolve_docs_dir(os.getenv("DOCS_DIR", "docs")),
    )


settings = load_settings()
