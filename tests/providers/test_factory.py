"""Unit tests for AI and backup storage provider factory."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from arc_life_diary.exceptions import DiaryError, UnknownProviderError
from arc_life_diary.providers.factory import get_ai_providers, get_backup_storage
from arc_life_diary.providers.gdrive import GoogleDriveStorage
from arc_life_diary.providers.mock import MockEmbeddingModel, MockLLMClient


def test_get_ai_providers_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with patch("arc_life_diary.providers.gemini.create_gemini_client") as mock_create_client:
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        with patch("arc_life_diary.providers.gemini.GeminiEmbeddingModel") as mock_embedder_cls:
            with patch("arc_life_diary.providers.gemini.GeminiLLMClient") as mock_llm_cls:
                embedder, llm = get_ai_providers("gemini")

                mock_create_client.assert_called_once_with(env_path=".env")
                mock_embedder_cls.assert_called_once_with(client=mock_client)
                mock_llm_cls.assert_called_once_with(client=mock_client)


def test_get_ai_providers_mock():
    embedder, llm = get_ai_providers("mock")
    assert isinstance(embedder, MockEmbeddingModel)
    assert isinstance(llm, MockLLMClient)
    assert embedder.dimensions == 768


def test_get_ai_providers_env_var(monkeypatch):
    monkeypatch.setenv("DIARY_AI_PROVIDER", "mock")
    embedder, llm = get_ai_providers()
    assert isinstance(embedder, MockEmbeddingModel)
    assert isinstance(llm, MockLLMClient)


def test_get_ai_providers_unknown():
    with pytest.raises(UnknownProviderError) as exc_info:
        get_ai_providers("ollama_unsupported")

    assert "Unknown AI provider: ollama_unsupported" in str(exc_info.value)
    assert isinstance(exc_info.value, DiaryError)
    assert isinstance(exc_info.value, ValueError)


def test_get_backup_storage_gdrive():
    with patch("arc_life_diary.providers.gdrive.GoogleDriveStorage.__init__", return_value=None) as mock_init:
        storage = get_backup_storage("gdrive", env_path=".env.custom")
        assert isinstance(storage, GoogleDriveStorage)
        mock_init.assert_called_once_with(env_path=".env.custom")


def test_get_backup_storage_env_var(monkeypatch):
    monkeypatch.setenv("DIARY_STORAGE_PROVIDER", "gdrive")
    with patch("arc_life_diary.providers.gdrive.GoogleDriveStorage.__init__", return_value=None) as mock_init:
        storage = get_backup_storage()
        assert isinstance(storage, GoogleDriveStorage)
        mock_init.assert_called_once_with(env_path=".env")


def test_get_backup_storage_unknown():
    with pytest.raises(UnknownProviderError) as exc_info:
        get_backup_storage("s3_unsupported")

    assert "Unknown storage provider: s3_unsupported" in str(exc_info.value)
    assert isinstance(exc_info.value, DiaryError)
    assert isinstance(exc_info.value, ValueError)
