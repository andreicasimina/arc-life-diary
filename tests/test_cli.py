"""Tests for CLI arguments, parsing, and execution error paths."""

from pathlib import Path
import pytest

from arc_life_diary.cli import build_parser, parse_cli_args, main


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


def test_cli_missing_env_error(monkeypatch, tmp_path: Path):
    # Change working directory to empty tmp_path without .env
    monkeypatch.chdir(tmp_path)
    exit_code = main(["sync"])
    assert exit_code == 1
