"""Tests for centralized exception hierarchy and error handling improvements."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from google.genai.errors import APIError
from googleapiclient.errors import HttpError

from arc_life_diary.backup import EmptyArchiveError as BackupEmptyArchiveError
from arc_life_diary.cli import main, parse_cli_args
from arc_life_diary.exceptions import (
    AIProviderError,
    BackupError,
    ConfigurationError,
    DecryptionError,
    DimensionMismatchError,
    DiaryError,
    EmptyArchiveError,
    GoogleDriveAuthError,
    PasswordMismatchError,
    ProviderAuthError,
    RemoteStorageError,
    RestoreCancelledError,
    StorageError,
    UnknownProviderError,
    ValidationError,
)
from arc_life_diary.providers.gdrive import GoogleDriveStorage
from arc_life_diary.providers.gemini import GeminiEmbeddingModel, GeminiLLMClient
from arc_life_diary.providers.mock import MockEmbeddingModel, MockLLMClient
from arc_life_diary.service import DiaryService, EmptyArchiveError as ServiceEmptyArchiveError
from arc_life_diary.store import DiaryStore, JournalEntry


def test_exception_hierarchy_inheritance():
    """Verify that all domain exceptions properly inherit from DiaryError."""
    assert issubclass(ConfigurationError, DiaryError)
    assert issubclass(ProviderAuthError, ConfigurationError)
    assert issubclass(GoogleDriveAuthError, ProviderAuthError)
    assert issubclass(UnknownProviderError, ConfigurationError)
    assert issubclass(UnknownProviderError, ValueError)

    assert issubclass(ValidationError, DiaryError)
    assert issubclass(ValidationError, ValueError)

    assert issubclass(StorageError, DiaryError)
    assert issubclass(DimensionMismatchError, StorageError)
    assert issubclass(DimensionMismatchError, ValueError)
    assert issubclass(RemoteStorageError, StorageError)

    assert issubclass(BackupError, DiaryError)
    assert issubclass(EmptyArchiveError, BackupError)
    assert issubclass(DecryptionError, BackupError)
    assert issubclass(PasswordMismatchError, BackupError)
    assert issubclass(RestoreCancelledError, BackupError)

    assert issubclass(AIProviderError, DiaryError)


def test_empty_archive_error_unification():
    """Verify that EmptyArchiveError across backup and service refers to the identical class."""
    assert ServiceEmptyArchiveError is EmptyArchiveError
    assert BackupEmptyArchiveError is EmptyArchiveError
    assert ServiceEmptyArchiveError is BackupEmptyArchiveError


def test_service_validation_errors(tmp_path: Path):
    """Verify that DiaryService raises ValidationError on empty query and missing directory."""
    embedder = MockEmbeddingModel(dimensions=4)
    db_path = tmp_path / "test.db"
    store = DiaryStore(db_path=db_path, dimensions=4)
    service = DiaryService(store=store, embedder=embedder)

    # Empty query raises ValidationError (which is both DiaryError and ValueError)
    with pytest.raises(ValidationError) as exc:
        service.query("   ")
    assert isinstance(exc.value, DiaryError)
    assert isinstance(exc.value, ValueError)

    with pytest.raises(ValidationError) as exc:
        service.search("")
    assert isinstance(exc.value, DiaryError)
    assert isinstance(exc.value, ValueError)

    # Non-existent directory raises ValidationError
    with pytest.raises(ValidationError) as exc:
        service.sync(tmp_path / "does_not_exist")
    assert isinstance(exc.value, DiaryError)

    store.close()


def test_store_dimension_mismatch_raised_consistently(tmp_path: Path):
    """Verify that DiaryStore consistently raises DimensionMismatchError on dimension issues."""
    db_path = tmp_path / "test.db"
    store = DiaryStore(db_path=db_path, dimensions=4)

    # Upsert with wrong dimension
    entry = JournalEntry(date="2024-01-01", title="T", content="C", content_hash="H")
    with pytest.raises(DimensionMismatchError) as exc:
        store.upsert_entries([(entry, [1.0, 2.0])])  # 2 dims instead of 4
    assert isinstance(exc.value, StorageError)
    assert isinstance(exc.value, ValueError)

    # Semantic search with wrong dimension
    with pytest.raises(DimensionMismatchError) as exc:
        store.search_semantic([1.0, 2.0])  # 2 dims instead of 4
    assert isinstance(exc.value, StorageError)
    assert isinstance(exc.value, ValueError)

    store.close()


def test_gdrive_storage_maps_http_errors(tmp_path: Path):
    """Verify that GoogleDriveStorage wraps HttpError in RemoteStorageError."""
    mock_service = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 404
    http_error_404 = HttpError(resp=mock_resp, content=b"Not Found")

    storage = GoogleDriveStorage(drive_service=mock_service)
    storage.folder_id = "folder123"

    archive_file = tmp_path / "test.7z"
    archive_file.write_bytes(b"dummy")

    # Test upload HttpError 404 maps to folder inaccessible
    mock_service.files().create.side_effect = http_error_404
    with pytest.raises(RemoteStorageError, match="folder 'folder123' not found or inaccessible"):
        storage.upload(archive_file, "test.7z")

    # Test list_backups HttpError
    mock_service.files().list.side_effect = http_error_404
    with pytest.raises(RemoteStorageError, match="Failed to query Google Drive backups"):
        storage.list_backups()

    # Test download HttpError 404
    mock_service.files().get_media.side_effect = http_error_404
    with pytest.raises(RemoteStorageError, match="Backup archive 'bad_id' not found"):
        storage.download("bad_id", tmp_path / "dest.7z")


def test_gemini_provider_maps_api_error():
    """Verify that Gemini provider wraps genai APIError in AIProviderError."""
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = APIError(429, {"message": "Quota exceeded"})
    mock_client.models.generate_content.side_effect = APIError(503, {"message": "Service unavailable"})

    embedder = GeminiEmbeddingModel(client=mock_client)
    with pytest.raises(AIProviderError, match="Gemini embedding API error"):
        embedder.embed_document("hello")

    with pytest.raises(AIProviderError, match="Gemini embedding API error"):
        embedder.embed_documents(["hello", "world"])

    llm = GeminiLLMClient(client=mock_client)
    with pytest.raises(AIProviderError, match="Gemini synthesis generation failed"):
        llm.generate_synthesis("prompt", "system instruction")


def test_cli_debug_flag(capsys):
    """Verify that CLI --debug flag prints tracebacks to stderr on error."""
    with patch("arc_life_diary.cli.get_ai_providers") as mock_factory:
        mock_factory.side_effect = DiaryError("Simulated failure")

        # Without --debug
        exit_code = main(["sync"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error: Simulated failure" in captured.err
        assert "Traceback" not in captured.err

        # With --debug
        exit_code_debug = main(["sync", "--debug"])
        assert exit_code_debug == 1
        captured_debug = capsys.readouterr()
        assert "Error: Simulated failure" in captured_debug.err
        assert "Traceback" in captured_debug.err
