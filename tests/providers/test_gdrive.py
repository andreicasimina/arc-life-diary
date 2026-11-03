"""Unit tests for Google Drive storage provider."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from arc_life_diary.providers.gdrive import (
    GoogleDriveAuthError,
    GoogleDriveStorage,
)


def test_missing_credentials_file_raises_auth_error(tmp_path):
    storage = GoogleDriveStorage(
        credentials_path=tmp_path / "nonexistent_credentials.json",
        token_path=tmp_path / "nonexistent_token.json",
        env_path=tmp_path / ".env",
    )
    with pytest.raises(GoogleDriveAuthError) as exc_info:
        _ = storage.service
    assert "credentials file" in str(exc_info.value)


def test_upload_with_folder_id(tmp_path):
    mock_service = MagicMock()
    mock_files = MagicMock()
    mock_service.files.return_value = mock_files
    mock_files.create.return_value.execute.return_value = {
        "id": "file_123",
        "name": "arc-life-diary_backup_2026-11-01_120000.7z",
        "createdTime": "2026-11-01T12:00:00Z",
        "size": "1024",
    }

    env_file = tmp_path / ".env"
    env_file.write_text("GDRIVE_FOLDER_ID=test_folder_id_xyz\n")

    storage = GoogleDriveStorage(
        env_path=env_file,
        drive_service=mock_service,
    )
    assert storage.folder_id == "test_folder_id_xyz"

    archive_file = tmp_path / "arc-life-diary_backup_2026-11-01_120000.7z"
    archive_file.write_bytes(b"dummy archive data")

    meta = storage.upload(archive_file, archive_file.name)

    assert meta.file_id == "file_123"
    assert meta.name == archive_file.name
    assert meta.size_bytes == 1024
    assert meta.created_at == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Verify create was called with parent folder ID
    create_call = mock_files.create.call_args[1]
    assert create_call["body"]["parents"] == ["test_folder_id_xyz"]
    assert create_call["body"]["name"] == archive_file.name


def test_upload_without_folder_id_defaults_to_root(tmp_path):
    mock_service = MagicMock()
    mock_files = MagicMock()
    mock_service.files.return_value = mock_files
    mock_files.create.return_value.execute.return_value = {
        "id": "file_root_1",
        "name": "arc-life-diary_backup_2026-11-01_120000.7z",
        "createdTime": "2026-11-01T12:00:00Z",
        "size": "512",
    }

    storage = GoogleDriveStorage(
        env_path=tmp_path / "nonexistent.env",
        drive_service=mock_service,
    )
    assert storage.folder_id is None

    archive_file = tmp_path / "arc-life-diary_backup_2026-11-01_120000.7z"
    archive_file.write_bytes(b"data")

    meta = storage.upload(archive_file, archive_file.name)
    assert meta.file_id == "file_root_1"

    create_call = mock_files.create.call_args[1]
    assert create_call["body"]["parents"] == ["root"]


def test_list_backups_filters_and_sorts(tmp_path):
    mock_service = MagicMock()
    mock_files = MagicMock()
    mock_service.files.return_value = mock_files
    mock_files.list.return_value.execute.return_value = {
        "files": [
            {
                "id": "file_older",
                "name": "arc-life-diary_backup_2026-10-01_100000.7z",
                "createdTime": "2026-10-01T10:00:00Z",
                "size": "2048",
            },
            {
                "id": "file_newer",
                "name": "arc-life-diary_backup_2026-11-01_100000.7z",
                "createdTime": "2026-11-01T10:00:00Z",
                "size": "4096",
            },
            {
                # Invalid name, should be ignored
                "id": "file_invalid",
                "name": "some_other_document.pdf",
                "createdTime": "2026-11-01T11:00:00Z",
                "size": "100",
            },
        ]
    }

    storage = GoogleDriveStorage(
        env_path=tmp_path / ".env",
        drive_service=mock_service,
    )

    backups = storage.list_backups()
    assert len(backups) == 2
    # Verify newest first
    assert backups[0].file_id == "file_newer"
    assert backups[1].file_id == "file_older"


def test_download_backup(tmp_path):
    mock_service = MagicMock()
    mock_files = MagicMock()
    mock_service.files.return_value = mock_files

    with patch("arc_life_diary.providers.gdrive.MediaIoBaseDownload") as mock_downloader_cls:
        mock_downloader = MagicMock()
        mock_downloader.next_chunk.return_value = (None, True)
        mock_downloader_cls.return_value = mock_downloader

        storage = GoogleDriveStorage(
            env_path=tmp_path / ".env",
            drive_service=mock_service,
        )

        dest_file = tmp_path / "downloads" / "test.7z"
        result_path = storage.download("file_abc_123", dest_file)

        assert result_path == dest_file
        mock_files.get_media.assert_called_once_with(fileId="file_abc_123")
