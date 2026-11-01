"""Tests for Gemini provider http options and retry configuration."""

from unittest.mock import MagicMock
from google.genai import types

from arc_life_diary.providers.gemini import (
    GeminiEmbeddingModel,
    GeminiLLMClient,
    default_http_options,
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
