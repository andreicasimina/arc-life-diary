"""SQLite storage layer with sqlite-vec extension and dynamic vector dimensioning."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional, Union
import sqlite_vec

from arc_life_diary.parser import JournalEntry


class DimensionMismatchError(Exception):
    """Raised when existing database dimensions do not match current embedder dimensions."""
    pass


@dataclass(frozen=True)
class SearchResult:
    """Represents a retrieved entry with vector distance."""

    date: str
    title: str
    content: str
    distance: float


class DiaryStore:
    """Manages the SQLite database, schema, and sqlite-vec virtual table."""

    def __init__(self, db_path: Union[str, Path] = "diary.db", dimensions: int = 768):
        self.db_path = str(db_path)
        self.dimensions = dimensions
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_sqlite_vec()
        self._init_schema()

    def _init_sqlite_vec(self) -> None:
        """Loads sqlite-vec extension into the SQLite connection."""
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

    def _init_schema(self) -> None:
        """Initializes tables and verifies embedding dimensions."""
        with self.conn:
            # Metadata table to store configuration and dimensions
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

            # Check existing dimensions
            cur = self.conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'embedding_dimensions';"
            )
            row = cur.fetchone()
            if row is not None:
                stored_dims = int(row["value"])
                if stored_dims != self.dimensions:
                    raise DimensionMismatchError(
                        f"Database dimension mismatch: stored={stored_dims}, "
                        f"requested={self.dimensions}. "
                        "Please delete the existing database or rebuild the index."
                    )
            else:
                self.conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES ('embedding_dimensions', ?);",
                    (str(self.dimensions),),
                )

            # Entries table: date (YYYY-MM-DD) is the unique primary key
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    date TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT '',
                    content_hash TEXT NOT NULL,
                    raw_content TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Virtual table using sqlite-vec vec0
            # vec_entries id maps to entries.rowid
            self.conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_entries USING vec0(
                    id INTEGER PRIMARY KEY,
                    embedding float[{self.dimensions}] distance_metric=cosine
                );
                """
            )

    def get_stored_hashes(self) -> Dict[str, str]:
        """Returns a mapping of {date: content_hash} for all stored entries."""
        cur = self.conn.execute("SELECT date, content_hash FROM entries;")
        return {row["date"]: row["content_hash"] for row in cur.fetchall()}

    def upsert_entry(self, entry: JournalEntry, embedding: List[float]) -> None:
        """Upserts an entry into SQLite and updates its embedding in vec_entries."""
        if len(embedding) != self.dimensions:
            raise ValueError(
                f"Vector dimension {len(embedding)} does not match store dimension {self.dimensions}"
            )

        with self.conn:
            # Upsert into entries and get the rowid
            cur = self.conn.execute(
                """
                INSERT INTO entries (date, title, content_hash, raw_content, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(date) DO UPDATE SET
                    title = excluded.title,
                    content_hash = excluded.content_hash,
                    raw_content = excluded.raw_content,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING rowid;
                """,
                (entry.date, entry.title, entry.content_hash, entry.content),
            )
            rowid = cur.fetchone()["rowid"]

            # Remove existing vector for this rowid if present, then insert new vector
            self.conn.execute("DELETE FROM vec_entries WHERE id = ?;", (rowid,))
            self.conn.execute(
                "INSERT INTO vec_entries (id, embedding) VALUES (?, ?);",
                (rowid, sqlite_vec.serialize_float32(embedding)),
            )

    def delete_entry(self, date: str) -> bool:
        """Deletes an entry and its vector by date. Returns True if deleted."""
        with self.conn:
            cur = self.conn.execute("SELECT rowid FROM entries WHERE date = ?;", (date,))
            row = cur.fetchone()
            if row is None:
                return False
            rowid = row["rowid"]

            self.conn.execute("DELETE FROM vec_entries WHERE id = ?;", (rowid,))
            self.conn.execute("DELETE FROM entries WHERE date = ?;", (date,))
            return True

    def search_semantic(self, query_vector: List[float], limit: int = 5) -> List[SearchResult]:
        """Performs semantic cosine search and returns up to limit matching entries."""
        if len(query_vector) != self.dimensions:
            raise ValueError(
                f"Query vector dimension {len(query_vector)} does not match store dimension {self.dimensions}"
            )

        cur = self.conn.execute(
            """
            SELECT
                e.date,
                e.title,
                e.raw_content,
                v.distance
            FROM vec_entries v
            JOIN entries e ON e.rowid = v.id
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance;
            """,
            (sqlite_vec.serialize_float32(query_vector), limit),
        )

        results: List[SearchResult] = []
        for row in cur.fetchall():
            results.append(
                SearchResult(
                    date=row["date"],
                    title=row["title"],
                    content=row["raw_content"],
                    distance=float(row["distance"]),
                )
            )
        return results

    def count_entries(self) -> int:
        """Returns the total number of entries in the database."""
        cur = self.conn.execute("SELECT COUNT(*) AS total FROM entries;")
        return cur.fetchone()["total"]

    def close(self) -> None:
        """Closes the database connection."""
        self.conn.close()
