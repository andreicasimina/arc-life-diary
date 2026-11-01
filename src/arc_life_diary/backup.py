"""Secure client-side encrypted backup and restore service.

Packages discrete Markdown journal entries into AES-256 encrypted 7z archives
with header encryption enabled, and delegates remote storage operations to
modular BaseBackupStorage implementations.
"""

from datetime import datetime
import os
from pathlib import Path
import re
import tempfile
from typing import Callable, List, Optional

import py7zr

from arc_life_diary.interfaces import BaseBackupStorage, RemoteBackupMetadata


class BackupError(Exception):
    """Base exception for backup and restore operations."""
    pass


class DecryptionError(BackupError):
    """Raised when archive decryption fails due to invalid password or corruption."""
    pass


class PasswordMismatchError(BackupError):
    """Raised when password confirmation does not match."""
    pass


class EmptyArchiveError(BackupError):
    """Raised when entries directory is empty during backup."""
    pass


class RestoreCancelledError(BackupError):
    """Raised when restore is cancelled by the user upon overwrite prompt."""
    pass


BACKUP_FILENAME_REGEX = re.compile(r"^arc-life-diary_backup_\d{4}-\d{2}-\d{2}_\d{6}\.7z$")


def generate_backup_filename(timestamp: Optional[datetime] = None) -> str:
    """Generates standard backup filename: arc-life-diary_backup_YYYY-MM-DD_HHMMSS.7z"""
    ts = timestamp or datetime.now()
    formatted = ts.strftime("%Y-%m-%d_%H%M%S")
    return f"arc-life-diary_backup_{formatted}.7z"


def is_valid_backup_filename(filename: str) -> bool:
    """Checks whether a filename matches the standard backup naming convention."""
    return bool(BACKUP_FILENAME_REGEX.match(filename))


def create_encrypted_archive(entries_dir: Path, output_path: Path, password: str) -> Path:
    """Packages all markdown entry files from entries_dir into an encrypted 7z archive.

    Uses AES-256 and enables header_encryption=True to fully mask filenames and metadata.
    """
    if not entries_dir.exists() or not entries_dir.is_dir():
        raise EmptyArchiveError(f"Entries directory '{entries_dir}' does not exist.")

    md_files = sorted(entries_dir.glob("*.md"))
    if not md_files:
        raise EmptyArchiveError(f"No markdown entries found in '{entries_dir}'.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with py7zr.SevenZipFile(output_path, mode="w", password=password, header_encryption=True) as archive:
        for file_path in md_files:
            # Store with file basename so restore unrolls flat into entries directory
            archive.write(file_path, arcname=file_path.name)

    return output_path


def extract_encrypted_archive(
    archive_path: Path,
    destination_dir: Path,
    password: str,
    overwrite_confirm_fn: Optional[Callable[[List[str]], bool]] = None,
) -> List[Path]:
    """Decrypts and unpacks an encrypted 7z archive into destination_dir.

    Args:
        archive_path: Path to .7z archive file.
        destination_dir: Directory where markdown files should be extracted.
        password: User-provided decryption password.
        overwrite_confirm_fn: Optional callback taking conflicting filenames and returning bool.

    Returns:
        List of Path objects for the extracted files.
    """
    if not archive_path.exists():
        raise BackupError(f"Archive file not found: {archive_path}")

    destination_dir.mkdir(parents=True, exist_ok=True)

    try:
        with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
            filenames = archive.getnames()
    except (
        py7zr.exceptions.Bad7zFile,
        py7zr.exceptions.PasswordRequired,
        py7zr.exceptions.ArchiveError,
        py7zr.exceptions.DecompressionError,
        py7zr.exceptions.CrcError,
        TypeError,
        ValueError,
    ) as e:
        raise DecryptionError("Decryption failed. Incorrect password or corrupted archive.") from e
    except Exception as e:
        raise DecryptionError(f"Decryption failed: {e}") from e

    # Check for overwrite conflicts with existing files in destination directory
    conflicts = [name for name in filenames if (destination_dir / name).exists()]
    if conflicts and overwrite_confirm_fn is not None:
        confirmed = overwrite_confirm_fn(conflicts)
        if not confirmed:
            raise RestoreCancelledError("Restore cancelled by user: overwrite confirmation declined.")

    try:
        with py7zr.SevenZipFile(archive_path, mode="r", password=password) as archive:
            archive.extractall(path=destination_dir)
    except Exception as e:
        raise DecryptionError("Decryption failed during extraction. Incorrect password or corrupted archive.") from e

    return [destination_dir / name for name in filenames]


class BackupService:
    """Orchestrates backup packaging, encryption, remote storage, and recovery."""

    def __init__(self, storage: BaseBackupStorage):
        self.storage = storage

    def create_backup(
        self,
        entries_dir: Path,
        password: str,
        confirm_password: Optional[str] = None,
    ) -> RemoteBackupMetadata:
        """Packages, encrypts, and uploads entries to the configured remote storage."""
        if confirm_password is not None and password != confirm_password:
            raise PasswordMismatchError("Backup encryption passwords do not match.")

        if not password:
            raise BackupError("Encryption password cannot be empty.")

        filename = generate_backup_filename()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_archive_path = Path(temp_dir) / filename
            create_encrypted_archive(
                entries_dir=entries_dir,
                output_path=temp_archive_path,
                password=password,
            )

            metadata = self.storage.upload(
                local_path=temp_archive_path,
                remote_filename=filename,
            )
            return metadata

    def list_backups(self) -> List[RemoteBackupMetadata]:
        """Lists available backup archives on the remote storage."""
        return self.storage.list_backups()

    def restore_backup(
        self,
        destination_dir: Path,
        password: str,
        file_id: Optional[str] = None,
        latest: bool = False,
        overwrite_confirm_fn: Optional[Callable[[List[str]], bool]] = None,
    ) -> List[Path]:
        """Downloads, decrypts, and unpacks a remote backup into destination_dir."""
        if not password:
            raise DecryptionError("Decryption password cannot be empty.")

        target_file_id = file_id
        if latest or not target_file_id:
            backups = self.list_backups()
            if not backups:
                raise BackupError("No backups found in remote storage.")
            target_file_id = backups[0].file_id

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_archive_path = Path(temp_dir) / "downloaded_backup.7z"
            self.storage.download(target_file_id, temp_archive_path)

            extracted_files = extract_encrypted_archive(
                archive_path=temp_archive_path,
                destination_dir=destination_dir,
                password=password,
                overwrite_confirm_fn=overwrite_confirm_fn,
            )
            return extracted_files
