"""Shared pytest configuration."""

from pathlib import Path

from dotenv import load_dotenv

# For convenience, load .env from the repo root
load_dotenv(Path(__file__).parents[2] / ".env")
