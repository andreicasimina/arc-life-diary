"""Markdown journal entry parser with frontmatter extraction and hashing."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import List, Optional
import yaml


# Pattern for YYYY-MM-DD
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class JournalEntry:
    """Represents a discrete daily journal entry."""

    date: str  # YYYY-MM-DD, uniquely identifies the entry
    title: str
    content: str
    content_hash: str


def compute_content_hash(text: str) -> str:
    """Computes SHA-256 hash of entry text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_entry_content(raw_text: str, entry_date: str) -> JournalEntry:
    """Parses raw Markdown content, extracting frontmatter title if present.

    The entry_date is established strictly from the filename.
    """
    frontmatter = {}
    body = raw_text

    # Check for YAML frontmatter between --- markers
    if raw_text.startswith("---"):
        parts = raw_text.split("---", 2)
        if len(parts) >= 3:
            fm_str = parts[1]
            body = parts[2].lstrip()
            try:
                parsed = yaml.safe_load(fm_str)
                if isinstance(parsed, dict):
                    frontmatter = parsed
            except Exception:
                # If frontmatter cannot be parsed, treat as regular text
                body = raw_text

    title = str(frontmatter.get("title", "")).strip()

    # Clean body text (strip leading/trailing whitespace)
    cleaned_content = body.strip()

    # Compute hash of the raw text so any edit triggers update
    content_hash = compute_content_hash(raw_text)

    return JournalEntry(
        date=entry_date,
        title=title,
        content=cleaned_content,
        content_hash=content_hash,
    )


def parse_entry_file(file_path: Path) -> Optional[JournalEntry]:
    """Reads and parses an entry markdown file."""
    file_name = file_path.stem
    if not DATE_PATTERN.match(file_name):
        return None

    raw_text = file_path.read_text(encoding="utf-8")
    return parse_entry_content(raw_text, entry_date=file_name)


def scan_entries_directory(dir_path: Path) -> List[JournalEntry]:
    """Scans directory for YYYY-MM-DD.md files and parses them."""
    if not dir_path.is_dir():
        return []

    entries: List[JournalEntry] = []
    for file_path in sorted(dir_path.glob("*.md")):
        entry = parse_entry_file(file_path)
        if entry is not None:
            entries.append(entry)

    return entries
