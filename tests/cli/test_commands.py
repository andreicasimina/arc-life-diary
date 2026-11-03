"""Integration and execution wiring tests for CLI commands (sync, query, backup, restore)."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from arc_life_diary.backup import DecryptionError
from arc_life_diary.cli import main
from arc_life_diary.interfaces import RemoteBackupMetadata


# --- Sync & Query Command Wiring ---

def test_cli_ai_provider_resolution(tmp_path: Path):
    mock_embedder = MagicMock()
    mock_embedder.dimensions = 768
    mock_llm = MagicMock()

    with patch("arc_life_diary.cli.get_ai_providers", return_value=(mock_embedder, mock_llm)) as mock_factory:
        with patch("arc_life_diary.cli.DiaryStore"):
            with patch("arc_life_diary.cli.DiaryService") as mock_service_cls:
                mock_service = MagicMock()
                mock_stats = MagicMock()
                mock_stats.scanned = 0
                mock_stats.added = 0
                mock_stats.updated = 0
                mock_stats.deleted = 0
                mock_stats.unchanged = 0
                mock_service.sync.return_value = mock_stats
                mock_service_cls.return_value = mock_service

                exit_code = main(["sync", "--dir", str(tmp_path)])
                assert exit_code == 0

                mock_factory.assert_called_once_with()
                mock_service_cls.assert_called_once()
                _, kwargs = mock_service_cls.call_args
                assert kwargs["embedder"] is mock_embedder
                assert kwargs["llm"] is mock_llm


def test_cli_missing_env_error(monkeypatch, tmp_path: Path):
    # Change working directory to empty tmp_path without .env
    monkeypatch.chdir(tmp_path)
    exit_code = main(["sync"])
    assert exit_code == 1


# --- Backup Subcommand Wiring ---

def test_cli_backup_empty_password(capsys):
    with patch("getpass.getpass", return_value=""):
        exit_code = main(["backup"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Password cannot be empty" in captured.err


def test_cli_backup_password_mismatch(capsys):
    with patch("getpass.getpass", side_effect=["pass1", "pass2"]):
        exit_code = main(["backup"])
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Passwords do not match" in captured.err


def test_cli_backup_success(tmp_path, capsys):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    (entries_dir / "2026-01-01.md").write_text("Test entry")

    mock_metadata = RemoteBackupMetadata(
        file_id="gdrive_file_999",
        name="arc-life-diary_backup_2026-11-01_120000.7z",
        created_at=datetime.now(),
        size_bytes=2048,
    )

    with patch("getpass.getpass", side_effect=["secure_pass", "secure_pass"]):
        with patch("arc_life_diary.cli.get_backup_storage"):
            with patch("arc_life_diary.cli.BackupService") as mock_service_cls:
                mock_service = MagicMock()
                mock_service.create_backup.return_value = mock_metadata
                mock_service_cls.return_value = mock_service

                exit_code = main(["backup", "--dir", str(entries_dir)])

                assert exit_code == 0
                captured = capsys.readouterr()
                assert "Backup uploaded successfully" in captured.out
                assert "arc-life-diary_backup_2026-11-01_120000.7z" in captured.out
                assert "gdrive_file_999" in captured.out


# --- Restore Subcommand Wiring ---

def test_cli_restore_no_backups(capsys):
    with patch("arc_life_diary.cli.get_backup_storage"):
        with patch("arc_life_diary.cli.BackupService") as mock_service_cls:
            mock_service = MagicMock()
            mock_service.list_backups.return_value = []
            mock_service_cls.return_value = mock_service

            exit_code = main(["restore"])
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "No backups found" in captured.err or "No backups found" in captured.out


def test_cli_restore_latest_success(tmp_path, capsys):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()

    mock_backups = [
        RemoteBackupMetadata(
            file_id="file_latest",
            name="arc-life-diary_backup_2026-11-01_120000.7z",
            created_at=datetime(2026, 11, 1, 12, 0, 0),
            size_bytes=1024,
        )
    ]

    with patch("getpass.getpass", return_value="my_pass"):
        with patch("arc_life_diary.cli.get_backup_storage"):
            with patch("arc_life_diary.cli.BackupService") as mock_service_cls:
                mock_service = MagicMock()
                mock_service.list_backups.return_value = mock_backups
                mock_service.restore_backup.return_value = [entries_dir / "2026-01-01.md"]
                mock_service_cls.return_value = mock_service

                exit_code = main(["restore", "--latest", "--dir", str(entries_dir)])
                assert exit_code == 0
                captured = capsys.readouterr()
                assert "Successfully restored 1 entries" in captured.out
                assert "diary sync" in captured.out
                mock_service.restore_backup.assert_called_once()
                call_kwargs = mock_service.restore_backup.call_args[1]
                assert call_kwargs["file_id"] == "file_latest"
                assert call_kwargs["password"] == "my_pass"


def test_cli_restore_decryption_error(tmp_path, capsys):
    mock_backups = [
        RemoteBackupMetadata(
            file_id="file_1",
            name="arc-life-diary_backup_2026-11-01_120000.7z",
            created_at=datetime(2026, 11, 1, 12, 0, 0),
            size_bytes=1024,
        )
    ]

    with patch("getpass.getpass", return_value="wrong_pass"):
        with patch("arc_life_diary.cli.get_backup_storage"):
            with patch("arc_life_diary.cli.BackupService") as mock_service_cls:
                mock_service = MagicMock()
                mock_service.list_backups.return_value = mock_backups
                mock_service.restore_backup.side_effect = DecryptionError("Incorrect password")
                mock_service_cls.return_value = mock_service

                exit_code = main(["restore", "--latest"])
                assert exit_code == 1
                captured = capsys.readouterr()
                assert "Error: Incorrect password" in captured.err
