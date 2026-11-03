"""Tests for Gemini provider http options, client injection, and environment resolution."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from google.genai import types

from arc_life_diary.providers.gemini import (
    GeminiEmbeddingModel,
    GeminiLLMClient,
    ProviderAuthError,
    create_gemini_client,
    default_http_options,
    load_env_api_key,
)


def test_default_http_options():
    opts = default_http_options()
    assert isinstance(opts, types.HttpOptions)
    assert opts.retry_options is not None
    assert opts.retry_options.attempts == 5
    assert 429 in opts.retry_options.http_status_codes
    assert 503 in opts.retry_options.http_status_codes
    assert opts.retry_options.initial_delay == 10.0
    assert opts.retry_options.max_delay == 60.0


def test_gemini_embedding_client_injection():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_emb = MagicMock()
    mock_emb.values = [0.1] * 768
    mock_response.embeddings = [mock_emb]
    mock_client.models.embed_content.return_value = mock_response

    embedder = GeminiEmbeddingModel(client=mock_client)
    res = embedder.embed_document("test entry")

    assert len(res) == 768
    assert mock_client.models.embed_content.called


def test_gemini_llm_client_injection():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Synthesized reflection."
    mock_client.models.generate_content.return_value = mock_response

    llm = GeminiLLMClient(client=mock_client)
    res = llm.generate_synthesis("prompt", "system instruction")

    assert res == "Synthesized reflection."
    assert mock_client.models.generate_content.called


def test_load_env_api_key_from_process_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "process-env-key-123")
    key = load_env_api_key(env_path="/nonexistent/.env")
    assert key == "process-env-key-123"


def test_load_env_api_key_from_dotenv_file(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=file-loaded-key-456\n")

    key = load_env_api_key(env_path=env_file)
    assert key == "file-loaded-key-456"
    assert os.environ.get("GEMINI_API_KEY") == "file-loaded-key-456"


def test_load_env_api_key_missing_raises(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ProviderAuthError, match="GEMINI_API_KEY is not set"):
        load_env_api_key(env_path=tmp_path / ".env")


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


def test_shared_client_reuse():
    mock_client = MagicMock()
    embedder = GeminiEmbeddingModel(client=mock_client)
    llm = GeminiLLMClient(client=mock_client)

    assert embedder._client is llm._client
    assert embedder._client is mock_client
