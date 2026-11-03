"""Shared pytest configuration and hermetic test isolation fixtures."""

import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """Ensures host process environment variables do not leak into test cases."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GDRIVE_FOLDER_ID", raising=False)
    monkeypatch.delenv("DIARY_ENTRIES_DIR", raising=False)
    monkeypatch.delenv("DIARY_DB_PATH", raising=False)
