"""Load configuration (config.yaml) and resolve project paths.

Secrets come from the repo-root .env (never hardcoded); tunables from config.yaml.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # projects/youtube-knowledge/
REPO_ROOT = PROJECT_ROOT.parent.parent                  # Transcendent/


def load_config() -> dict:
    load_dotenv(REPO_ROOT / ".env")  # optional; only needed for API metadata/comments
    with open(PROJECT_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_paths(cfg: dict) -> dict[str, Path]:
    """config.yaml paths are relative to the subproject root."""
    return {k: (PROJECT_ROOT / v) for k, v in cfg["paths"].items()}
