"""
Path: core/config.py
Centralized settings for migration + validation. Values come from environment variables with safe defaults.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    # Providers: "dummy" (default), "llm" (xai/openai/gemini via PROVIDER_NAME), or "ts-migrate"
    CONVERTER: str = os.getenv("AIO_CONVERTER", "dummy")
    PROVIDER_NAME: str = os.getenv("AIO_PROVIDER", "openai")  # xai|openai|gemini
    MAX_WORKERS: int = int(os.getenv("AIO_MAX_WORKERS", "8"))

    # Validation tools
    TSC_CMD: str = os.getenv("AIO_TSC", "tsc")
    TEST_CMD: str = os.getenv("AIO_TEST_CMD", "")  # e.g., "npx vitest run" or "npm test -- --run"

    # Git settings (optional)
    GIT_PROVIDER: str = os.getenv("AIO_GIT_PROVIDER", "github")  # github|gitlab|local
    GIT_REPO: str = os.getenv("AIO_GIT_REPO", "")  # e.g., "owner/name"
    GIT_TOKEN: str = os.getenv("AIO_GIT_TOKEN", "")
    GIT_MAIN_BRANCH: str = os.getenv("AIO_GIT_MAIN", "main")

    # Paths
    PROJECT_ROOT: Path = Path(os.getenv("AIO_PROJECT_ROOT", ".")).resolve()
    REPORTS_DIR: Path = Path(os.getenv("AIO_REPORTS_DIR", "./reports")).resolve()

    # Behavior flags
    DRY_RUN: bool = os.getenv("AIO_DRY_RUN", "true").lower() in {"1", "true", "yes"}
    WRITE_TESTS: bool = os.getenv("AIO_WRITE_TESTS", "true").lower() in {"1", "true", "yes"}


def get_settings() -> Settings:
    return Settings()

