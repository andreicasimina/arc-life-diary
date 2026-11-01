"""Unit tests for client-side encrypted backup and restore."""

from datetime import datetime
from pathlib import Path
import pytest

from arc_life_diary.backup import (
    BackupError,
    BackupService,
    DecryptionError,
    EmptyArchiveError,
    PasswordMismatchError,
    RestoreCancelledError,
    create_encrypted_archive,
    extract_encrypted_archive,
    generate_backup_filename,
    is_valid_backup_filename,
)
from arc_life_diary.interfaces import BaseBackupStorage, RemoteBackupMetadata


class DummyStorage(BaseBackupStorage):
    """In-memory mock storage for backup service tests."""

    def __init__(self):
        self.files = {}
        self.upload_calls = []

    def upload(self, local_path: Path, remote_filename: str) -> RemoteBackupMetadata:
        data = local_path.read_bytes()
        file_id = f"dummy_{len(self.files) + 1}"
        metadata = RemoteBackupMetadata(
            file_id=file_id,
            name=remote_filename,
            created_at=datetime.now(),
            size_bytes=len(data),
        )
        self.files[file_id] = (metadata, data)
        self.upload_calls.append((local_path, remote_filename))
        return metadata

    def list_backups(self):
        return [meta for meta, _ in sorted(self.files.values(), key=lambda x: x[0].created_at, reverse=True)]

    def download(self, file_id: str, destination_path: Path) -> Path:
        if file_id not in self.files:
            raise BackupError(f"File {file_id} not found in dummy storage")
        _, data = self.files[file_id]
        destination_path.write_bytes(data)
        return destination_path


def test_backup_filename_format():
    dt = datetime(2026, 11, 1, 15, 30, 45)
    name = generate_backup_filename(dt)
    assert name == "arc-life-diary_backup_2026-11-01_153045.7z"
    assert is_valid_backup_filename(name)
    assert not is_valid_backup_filename("random_archive.7z")


def test_create_archive_empty_dir_raises(tmp_path):
    empty_dir = tmp_path / "entries"
    empty_dir.mkdir()
    out_archive = tmp_path / "test.7z"

    with pytest.raises(EmptyArchiveError):
        create_encrypted_archive(empty_dir, out_archive, password="test")


def test_create_and_extract_archive_roundtrip(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    (entries_dir / "2026-01-01.md").write_text("# New Year\nReflections.")
    (entries_dir / "2026-01-02.md").write_text("# Day Two\nMore thoughts.")

    archive_path = tmp_path / "backup.7z"
    create_encrypted_archive(entries_dir, archive_path, password="secret_password_123")

    assert archive_path.exists()
    assert archive_path.stat().st_size > 0

    # Wrong password extraction fails
    restore_dir = tmp_path / "restored"
    with pytest.raises(DecryptionError):
        extract_encrypted_archive(archive_path, restore_dir, password="wrong_password")

    # Correct password succeeds
    restored_files = extract_encrypted_archive(archive_path, restore_dir, password="secret_password_123")
    assert len(restored_files) == 2
    assert (restore_dir / "2026-01-01.md").read_text() == "# New Year\nReflections."
    assert (restore_dir / "2026-01-02.md").read_text() == "# Day Two\nMore thoughts."


def test_extract_archive_overwrite_confirmation_declined(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    (entries_dir / "2026-01-01.md").write_text("Original content")

    archive_path = tmp_path / "backup.7z"
    create_encrypted_archive(entries_dir, archive_path, password="pass")

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    existing_file = restore_dir / "2026-01-01.md"
    existing_file.write_text("Existing un-overwritten content")

    # When confirmation returns False
    with pytest.raises(RestoreCancelledError):
        extract_encrypted_archive(
            archive_path,
            restore_dir,
            password="pass",
            overwrite_confirm_fn=lambda conflicts: False,
        )

    # Existing content must be preserved
    assert existing_file.read_text() == "Existing un-overwritten content"


def test_extract_archive_overwrite_confirmation_accepted(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    (entries_dir / "2026-01-01.md").write_text("Updated backup content")

    archive_path = tmp_path / "backup.7z"
    create_encrypted_archive(entries_dir, archive_path, password="pass")

    restore_dir = tmp_path / "restored"
    restore_dir.mkdir()
    existing_file = restore_dir / "2026-01-01.md"
    existing_file.write_text("Old content")

    # When confirmation returns True
    extract_encrypted_archive(
        archive_path,
        restore_dir,
        password="pass",
        overwrite_confirm_fn=lambda conflicts: True,
    )

    assert existing_file.read_text() == "Updated backup content"


def test_backup_service_flow(tmp_path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    (entries_dir / "2026-01-01.md").write_text("Entry")

    storage = DummyStorage()
    service = BackupService(storage=storage)

    # Password mismatch check
    with pytest.raises(PasswordMismatchError):
        service.create_backup(entries_dir, password="pass1", confirm_password="pass2")

    # Successful backup
    meta = service.create_backup(entries_dir, password="mypassword", confirm_password="mypassword")
    assert meta.file_id == "dummy_1"
    assert is_valid_backup_filename(meta.name)
    assert len(storage.list_backups()) == 1

    # Restore latest
    target_dir = tmp_path / "dest"
    restored = service.restore_backup(target_dir, password="mypassword", latest=True)
    assert len(restored) == 1
    assert (target_dir / "2026-01-01.md").read_text() == "Entry"
