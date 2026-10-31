"""Tests for DiaryService orchestration, sync caching, and synthesis."""

from pathlib import Path
import pytest

from arc_life_diary.providers.mock import MockEmbeddingModel, MockLLMClient
from arc_life_diary.service import DiaryService, EmptyArchiveError
from arc_life_diary.store import DiaryStore


def test_sync_incremental_caching(tmp_path: Path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    db_path = tmp_path / "test.db"

    # Create initial files
    (entries_dir / "2024-01-01.md").write_text("Happy new year!", encoding="utf-8")
    (entries_dir / "2024-01-02.md").write_text("Started new project.", encoding="utf-8")

    embedder = MockEmbeddingModel(dimensions=4)
    store = DiaryStore(db_path=db_path, dimensions=4)
    service = DiaryService(store=store, embedder=embedder)

    # First sync: both files added
    res1 = service.sync(entries_dir)
    assert res1.scanned == 2
    assert res1.added == 2
    assert res1.updated == 0
    assert res1.unchanged == 0
    assert res1.deleted == 0

    # Second sync without file modifications: zero redundant embeds
    res2 = service.sync(entries_dir)
    assert res2.scanned == 2
    assert res2.added == 0
    assert res2.updated == 0
    assert res2.unchanged == 2
    assert res2.deleted == 0

    # Modify one file and add a new one
    (entries_dir / "2024-01-01.md").write_text("Happy new year with extra reflections!", encoding="utf-8")
    (entries_dir / "2024-01-03.md").write_text("Third entry.", encoding="utf-8")

    res3 = service.sync(entries_dir)
    assert res3.scanned == 3
    assert res3.added == 1
    assert res3.updated == 1
    assert res3.unchanged == 1
    assert res3.deleted == 0

    # Delete one file
    (entries_dir / "2024-01-02.md").unlink()
    res4 = service.sync(entries_dir)
    assert res4.scanned == 2
    assert res4.added == 0
    assert res4.updated == 0
    assert res4.unchanged == 2
    assert res4.deleted == 1

    store.close()


def test_sync_empty_archive(tmp_path: Path):
    entries_dir = tmp_path / "empty_dir"
    entries_dir.mkdir()
    db_path = tmp_path / "test.db"

    embedder = MockEmbeddingModel(dimensions=4)
    store = DiaryStore(db_path=db_path, dimensions=4)
    service = DiaryService(store=store, embedder=embedder)

    with pytest.raises(EmptyArchiveError):
        service.sync(entries_dir)

    store.close()


def test_query_synthesis_formatting(tmp_path: Path):
    entries_dir = tmp_path / "entries"
    entries_dir.mkdir()
    db_path = tmp_path / "test.db"

    (entries_dir / "2021-04-15.md").write_text(
        "---\ntitle: Job Stress\n---\nFelt completely overwhelmed by unexpected production outages.",
        encoding="utf-8",
    )
    (entries_dir / "2024-02-10.md").write_text(
        "---\ntitle: Retrospective\n---\nReflecting back on 2021 outages; I handle stress much better now.",
        encoding="utf-8",
    )

    embedder = MockEmbeddingModel(dimensions=4)
    llm = MockLLMClient()
    store = DiaryStore(db_path=db_path, dimensions=4)
    service = DiaryService(store=store, embedder=embedder, llm=llm)

    service.sync(entries_dir)
    output = service.query("How did I handle stress over time?", limit=2)

    # Verification: output begins directly with commentary without analysis headers
    # and ends with programmatically appended ## Relevant Entries
    assert "Over time, an evident maturation" in output
    assert "## Relevant Entries" in output
    assert "- Date: 2021-04-15 | Title: Job Stress | Distance:" in output
    assert "- Date: 2024-02-10 | Title: Retrospective | Distance:" in output

    store.close()


def test_provider_decoupling():
    """Verify that core modules have zero vendor imports (e.g. google.genai)."""
    import inspect
    from arc_life_diary import parser, service, store

    for module in [parser, store, service]:
        source = inspect.getsource(module)
        assert "google.genai" not in source
        assert "google" not in source
