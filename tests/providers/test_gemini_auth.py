"""Tests for Gemini API key resolution, .env fallback, and client factory logic."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from arc_life_diary.exceptions import ProviderAuthError
from arc_life_diary.providers.gemini import (
    _resolve_api_key,
    create_gemini_client,
)


def test_resolve_api_key_from_process_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "process-env-key-123")
    key = _resolve_api_key(env_path="/nonexistent/.env")
    assert key == "process-env-key-123"


def test_resolve_api_key_from_dotenv_file(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=file-loaded-key-456\n")

    key = _resolve_api_key(env_path=env_file)
    assert key == "file-loaded-key-456"
    assert os.environ.get("GEMINI_API_KEY") == "file-loaded-key-456"


def test_resolve_api_key_missing_raises(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError, match="GEMINI_API_KEY is not set"):
        _resolve_api_key(env_path=tmp_path / ".env")


def test_create_gemini_client_with_explicit_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("arc_life_diary.providers.gemini.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        client = create_gemini_client(api_key="explicit-key-789")
        assert client is mock_instance
        mock_client_cls.assert_called_once()
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "explicit-key-789"


def test_create_gemini_client_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-key-321")
    with patch("arc_life_diary.providers.gemini.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        client = create_gemini_client()
        assert client is mock_instance
        _, kwargs = mock_client_cls.call_args
        assert kwargs["api_key"] == "env-key-321"


def test_create_gemini_client_missing_key_raises(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError, match="GEMINI_API_KEY is not set"):
        create_gemini_client(env_path=tmp_path / ".env")
