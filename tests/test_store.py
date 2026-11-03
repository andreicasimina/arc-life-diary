"""Tests for local SQLite + sqlite-vec vector store."""

from pathlib import Path
import pytest

from arc_life_diary.parser import JournalEntry
from arc_life_diary.store import DiaryStore, DimensionMismatchError, SearchResult


def test_store_initialization(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    store = DiaryStore(db_path=db_file, dimensions=4)
    assert store.dimensions == 4
    assert store.count_entries() == 0
    store.close()


def test_dimension_mismatch_error(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    store = DiaryStore(db_path=db_file, dimensions=4)
    store.close()

    # Reopening with different dimensions should raise DimensionMismatchError
    with pytest.raises(DimensionMismatchError) as exc_info:
        DiaryStore(db_path=db_file, dimensions=768)

    assert "Database dimension mismatch" in str(exc_info.value)


def test_upsert_and_hash_tracking(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    store = DiaryStore(db_path=db_file, dimensions=4)

    entry1 = JournalEntry(
        date="2024-01-01",
        title="New Year",
        content="First day of 2024.",
        content_hash="hash_v1",
    )
    store.upsert_entry(entry1, [1.0, 0.0, 0.0, 0.0])

    hashes = store.get_stored_hashes()
    assert hashes == {"2024-01-01": "hash_v1"}
    assert store.count_entries() == 1

    # Update entry with new content and hash
    entry1_updated = JournalEntry(
        date="2024-01-01",
        title="New Year (Updated)",
        content="First day of 2024 with more details.",
        content_hash="hash_v2",
    )
    store.upsert_entry(entry1_updated, [0.0, 1.0, 0.0, 0.0])

    hashes = store.get_stored_hashes()
    assert hashes == {"2024-01-01": "hash_v2"}
    assert store.count_entries() == 1

    store.close()


def test_search_semantic(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    store = DiaryStore(db_path=db_file, dimensions=3)

    e1 = JournalEntry(date="2021-05-01", title="Trip A", content="Visited the mountains.", content_hash="h1")
    e2 = JournalEntry(date="2022-06-01", title="Trip B", content="Beach vacation.", content_hash="h2")

    store.upsert_entry(e1, [1.0, 0.0, 0.0])
    store.upsert_entry(e2, [0.0, 1.0, 0.0])

    # Search close to [1.0, 0.0, 0.0]
    results = store.search_semantic([0.9, 0.1, 0.0], limit=2)
    assert len(results) == 2
    assert results[0].date == "2021-05-01"
    assert results[0].title == "Trip A"
    assert results[0].distance < results[1].distance

    store.close()


def test_delete_entry(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    store = DiaryStore(db_path=db_file, dimensions=3)

    e1 = JournalEntry(date="2023-01-01", title="Entry 1", content="Content 1", content_hash="h1")
    store.upsert_entry(e1, [1.0, 0.0, 0.0])
    assert store.count_entries() == 1

    assert store.delete_entry("2023-01-01") is True
    assert store.count_entries() == 0
    assert store.delete_entry("2023-01-01") is False

    store.close()


def test_context_manager_resource_release(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    with DiaryStore(db_path=db_file, dimensions=4) as store:
        assert store.count_entries() == 0

    # Ensure connection is closed after context exit
    import sqlite3

    with pytest.raises(sqlite3.ProgrammingError, match="Cannot operate on a closed database"):
        store.conn.execute("SELECT 1;")


def test_upsert_entries_batch(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    with DiaryStore(db_path=db_file, dimensions=3) as store:
        # Empty batch should be a no-op
        store.upsert_entries([])
        assert store.count_entries() == 0

        e1 = JournalEntry(date="2024-01-01", title="Day 1", content="Content 1", content_hash="h1")
        e2 = JournalEntry(date="2024-01-02", title="Day 2", content="Content 2", content_hash="h2")
        e3 = JournalEntry(date="2024-01-03", title="Day 3", content="Content 3", content_hash="h3")

        items = [
            (e1, [1.0, 0.0, 0.0]),
            (e2, [0.0, 1.0, 0.0]),
            (e3, [0.0, 0.0, 1.0]),
        ]
        store.upsert_entries(items)

        assert store.count_entries() == 3
        hashes = store.get_stored_hashes()
        assert hashes == {
            "2024-01-01": "h1",
            "2024-01-02": "h2",
            "2024-01-03": "h3",
        }

        # Verify semantic search works over batched items
        results = store.search_semantic([0.9, 0.1, 0.0], limit=1)
        assert len(results) == 1
        assert results[0].date == "2024-01-01"


def test_upsert_entries_rollback_on_dimension_mismatch(tmp_path: Path):
    db_file = tmp_path / "test_diary.db"
    with DiaryStore(db_path=db_file, dimensions=3) as store:
        initial_entry = JournalEntry(
            date="2024-01-01", title="Initial", content="Baseline", content_hash="h_base"
        )
        store.upsert_entry(initial_entry, [1.0, 0.0, 0.0])
        assert store.count_entries() == 1

        e_valid = JournalEntry(
            date="2024-01-02", title="Valid", content="Valid content", content_hash="h_val"
        )
        e_invalid = JournalEntry(
            date="2024-01-03", title="Invalid", content="Bad content", content_hash="h_inv"
        )

        # e_valid has 3 dims, e_invalid has 4 dims (mismatch)
        items = [
            (e_valid, [0.0, 1.0, 0.0]),
            (e_invalid, [0.0, 0.0, 1.0, 0.0]),
        ]

        with pytest.raises(ValueError, match="Vector dimension 4 does not match store dimension 3"):
            store.upsert_entries(items)

        # Confirm atomic rollback: e_valid must NOT be persisted
        assert store.count_entries() == 1
        hashes = store.get_stored_hashes()
        assert hashes == {"2024-01-01": "h_base"}
        assert "2024-01-02" not in hashes

