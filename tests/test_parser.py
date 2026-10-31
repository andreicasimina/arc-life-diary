"""Tests for Markdown parser and frontmatter extraction."""

import hashlib
from pathlib import Path
import pytest

from arc_life_diary.parser import (
    JournalEntry,
    compute_content_hash,
    parse_entry_content,
    parse_entry_file,
    scan_entries_directory,
)


def test_compute_content_hash():
    text = "Today was a productive day."
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert compute_content_hash(text) == expected


def test_parse_entry_content_with_frontmatter():
    raw_text = """---
title: Team Retro
date: 1999-01-01
---
Reflecting on the past sprint challenges."""
    # Date should be strictly taken from the passed entry_date, ignoring frontmatter date
    entry = parse_entry_content(raw_text, entry_date="2024-05-10")
    assert entry.date == "2024-05-10"
    assert entry.title == "Team Retro"
    assert entry.content == "Reflecting on the past sprint challenges."
    assert entry.content_hash == compute_content_hash(raw_text)


def test_parse_entry_content_without_frontmatter():
    raw_text = "今日は一日中コードを書いていた。集中できて満足。"
    entry = parse_entry_content(raw_text, entry_date="2023-11-20")
    assert entry.date == "2023-11-20"
    assert entry.title == ""
    assert entry.content == raw_text
    assert entry.content_hash == compute_content_hash(raw_text)


def test_parse_entry_file(tmp_path: Path):
    file_path = tmp_path / "2025-01-15.md"
    file_path.write_text(
        "---\ntitle: Tokyo Trip\n---\nVisited Akihabara and Shinjuku.",
        encoding="utf-8",
    )

    entry = parse_entry_file(file_path)
    assert entry is not None
    assert entry.date == "2025-01-15"
    assert entry.title == "Tokyo Trip"
    assert "Akihabara" in entry.content


def test_parse_entry_file_invalid_date(tmp_path: Path):
    file_path = tmp_path / "random-notes.md"
    file_path.write_text("Not a dated journal entry.", encoding="utf-8")

    entry = parse_entry_file(file_path)
    assert entry is None


def test_scan_entries_directory(tmp_path: Path):
    (tmp_path / "2022-03-01.md").write_text("March entry 1", encoding="utf-8")
    (tmp_path / "2022-03-02.md").write_text("March entry 2", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Ignored text file", encoding="utf-8")
    (tmp_path / "draft.md").write_text("Ignored non-dated md file", encoding="utf-8")

    entries = scan_entries_directory(tmp_path)
    assert len(entries) == 2
    dates = [e.date for e in entries]
    assert dates == ["2022-03-01", "2022-03-02"]
