"""Tests for CLI arguments, parsing, and execution error paths."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from arc_life_diary.cli import build_parser, parse_cli_args, load_config, main


def test_cli_argument_parsing():
    # Sync command
    args_sync = parse_cli_args(["sync", "--dir", "./my_entries"])
    assert args_sync.command == "sync"
    assert args_sync.dir == "./my_entries"

    # Query command explicit
    args_query = parse_cli_args(["query", "stress response", "--limit", "3"])
    assert args_query.command == "query"
    assert args_query.query_text == "stress response"
    assert args_query.limit == 3

    # Query shorthand: diary "stress response"
    args_short = parse_cli_args(["stress response"])
    assert args_short.command == "query"
    assert args_short.query_text == "stress response"
    assert args_short.limit == 5

    # Search command explicit
    args_search = parse_cli_args(["search", "stress response", "--limit", "4", "--dir", "./entries"])
    assert args_search.command == "search"
    assert args_search.query_text == "stress response"
    assert args_search.limit == 4
    assert args_search.dir == "./entries"


def test_load_config_env(monkeypatch):
    monkeypatch.setenv("DIARY_ENTRIES_DIR", "/custom/entries")
    monkeypatch.setenv("DIARY_DB_PATH", "/custom/diary.db")
    config = load_config()
    assert config["entries_dir"] == "/custom/entries"
    assert config["db_path"] == "/custom/diary.db"


def test_cli_shared_client_injected(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
    with patch("arc_life_diary.cli.create_gemini_client") as mock_create_client:
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        with patch("arc_life_diary.cli.GeminiEmbeddingModel") as mock_embedder_cls:
            with patch("arc_life_diary.cli.GeminiLLMClient") as mock_llm_cls:
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

                        # Ensure shared client was created once and passed to both models
                        mock_create_client.assert_called_once_with(env_path=".env")
                        mock_embedder_cls.assert_called_once_with(client=mock_client)
                        mock_llm_cls.assert_called_once_with(client=mock_client)


def test_cli_missing_env_error(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    # Change working directory to empty tmp_path without .env
    monkeypatch.chdir(tmp_path)
    exit_code = main(["sync"])
    assert exit_code == 1
