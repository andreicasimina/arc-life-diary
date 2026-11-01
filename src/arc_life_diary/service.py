"""Orchestration service layer for synchronization, retrieval, and synthesis.

Adheres strictly to the Dependency Inversion Principle with zero vendor SDK imports.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from arc_life_diary.interfaces import BaseEmbeddingModel, BaseLLMClient
from arc_life_diary.parser import JournalEntry, scan_entries_directory
from arc_life_diary.store import DiaryStore, SearchResult


class EmptyArchiveError(Exception):
    """Raised when the entries archive directory contains no markdown files."""
    pass


@dataclass(frozen=True)
class SyncResult:
    """Statistics summarizing synchronization execution."""

    scanned: int
    added: int
    updated: int
    deleted: int
    unchanged: int


SYSTEM_INSTRUCTION = """You are a personal journal introspection assistant.
Your task is to analyze the provided journal entries to answer the user's query about their life, thoughts, and emotional development.

Guidelines:
1. Differentiate between entry creation date (when the note was penned) and narrative memory date (when the event actually occurred in the past).
2. Trace an objective, chronological developmental progression, highlighting shifts in attitude, coping mechanisms, and emotional regulation across time.
3. Keep your synthesis to exactly one medium-length paragraph.
4. Write your entire response strictly in English, even if the source entries are in Japanese, English, or code-switched.
5. Do not include any headers or bullet lists. Start directly with your synthesis paragraph.
"""


def format_relevant_entries(entries: List[SearchResult]) -> str:
    """Programmatically formats the relevant entries metadata."""
    lines = ["## Relevant Entries"]
    for r in entries:
        title_part = f" | Title: {r.title}" if r.title else ""
        lines.append(f"- Date: {r.date}{title_part} | Distance: {r.distance:.4f}")
    return "\n".join(lines)


class DiaryService:
    """Coordinates storage, embedding generation, and LLM synthesis."""

    def __init__(
        self,
        store: DiaryStore,
        embedder: BaseEmbeddingModel,
        llm: Optional[BaseLLMClient] = None,
    ):
        self.store = store
        self.embedder = embedder
        self.llm = llm

    def sync(self, entries_dir: Union[str, Path]) -> SyncResult:
        """Incrementally synchronizes entry files with the vector database."""
        path = Path(entries_dir)
        if not path.exists():
            raise FileNotFoundError(f"Entries directory does not exist: {path.resolve()}")

        scanned_entries = scan_entries_directory(path)
        if not scanned_entries:
            raise EmptyArchiveError(f"No journal entries (YYYY-MM-DD.md) found in {path.resolve()}")

        stored_hashes = self.store.get_stored_hashes()
        scanned_dates = {e.date for e in scanned_entries}

        entries_to_add: List[JournalEntry] = []
        entries_to_update: List[JournalEntry] = []
        unchanged = 0

        for entry in scanned_entries:
            stored_hash = stored_hashes.get(entry.date)
            if stored_hash is None:
                entries_to_add.append(entry)
            elif stored_hash != entry.content_hash:
                entries_to_update.append(entry)
            else:
                unchanged += 1

        entries_to_embed = entries_to_add + entries_to_update
        if entries_to_embed:
            embeddings = self.embedder.embed_documents([e.content for e in entries_to_embed])
            for entry, embedding in zip(entries_to_embed, embeddings):
                self.store.upsert_entry(entry, embedding)

        added = len(entries_to_add)
        updated = len(entries_to_update)

        # Delete entries that no longer exist in the directory
        deleted = 0
        for stored_date in stored_hashes:
            if stored_date not in scanned_dates:
                self.store.delete_entry(stored_date)
                deleted += 1

        return SyncResult(
            scanned=len(scanned_entries),
            added=added,
            updated=updated,
            deleted=deleted,
            unchanged=unchanged,
        )

    def search(self, query_text: str, limit: int = 5) -> str:
        """Performs semantic search and returns formatted relevant entries without LLM synthesis."""
        if not query_text.strip():
            raise ValueError("Query string cannot be empty.")

        query_vector = self.embedder.embed_query(query_text)
        retrieved_entries = self.store.search_semantic(query_vector, limit=limit)

        if not retrieved_entries:
            return "No matching journal entries found in the archive."

        return format_relevant_entries(retrieved_entries)

    def query(self, query_text: str, limit: int = 5) -> str:
        """Searches entries and returns synthesized reflection with relevant entries."""
        if not query_text.strip():
            raise ValueError("Query string cannot be empty.")

        query_vector = self.embedder.embed_query(query_text)
        retrieved_entries = self.store.search_semantic(query_vector, limit=limit)

        if not retrieved_entries:
            return "No matching journal entries found in the archive."

        entries_section = format_relevant_entries(retrieved_entries)

        if self.llm is None:
            return entries_section

        # Build prompt with retrieved context
        context_blocks = []
        for r in retrieved_entries:
            title_part = f" ({r.title})" if r.title else ""
            context_blocks.append(
                f"--- Entry Date: {r.date}{title_part} [Cosine Distance: {r.distance:.4f}] ---\n"
                f"{r.content}\n"
            )

        context_str = "\n".join(context_blocks)
        prompt = (
            f"User Question: {query_text}\n\n"
            f"Here are the relevant journal entries retrieved from the user's personal archive:\n\n"
            f"{context_str}\n\n"
            "Synthesize an objective reflection tracing behavioral and perspective shifts across time."
        )

        llm_response = self.llm.generate_synthesis(prompt, system_instruction=SYSTEM_INSTRUCTION).strip()
        return f"{llm_response}\n\n{entries_section}"
