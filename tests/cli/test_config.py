"""Tests for CLI configuration loading and environment resolution."""

from pathlib import Path
from arc_life_diary.cli import load_config


def test_load_config_defaults(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config["entries_dir"] == "./entries"
    assert config["db_path"] == "./diary.db"


def test_load_config_env(monkeypatch):
    monkeypatch.setenv("DIARY_ENTRIES_DIR", "/custom/entries")
    monkeypatch.setenv("DIARY_DB_PATH", "/custom/diary.db")
    config = load_config()
    assert config["entries_dir"] == "/custom/entries"
    assert config["db_path"] == "/custom/diary.db"


def test_load_config_from_dotenv(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("DIARY_ENTRIES_DIR=./dotenv_entries\nDIARY_DB_PATH=./dotenv_diary.db\n")
    config = load_config()
    assert config["entries_dir"] == "./dotenv_entries"
    assert config["db_path"] == "./dotenv_diary.db"
