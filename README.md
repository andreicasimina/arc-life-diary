# arc-life-diary

A command-line introspection tool for personal journals. It semantically searches through your markdown journal entries across languages (English, Japanese, or mixed) and synthesizes developmental reflections tracing how your thoughts, perspectives, and coping mechanisms have evolved over time.

---

## What It Can Do

- **Cross-Lingual Semantic Search**: Ask questions in English and retrieve relevant entries written in English, Japanese, or mixed notes.
- **Temporal & Developmental Synthesis**: Synthesizes a coherent chronological narrative tracing behavioral and mindset shifts across years of entries.
- **Auditable Citations**: Lists the source journal entries for your query with dates, optional titles, and vector similarity metrics.
- **Fast, Local Vector Storage**: Uses local SQLite vector storage (`sqlite-vec`) with incremental caching so unchanged entries are not re-embedded.

---

## Quickstart

### 1. Installation

Install the package in editable mode:

```bash
pip install -e .
```

### 2. Configuration

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Add your Gemini API key:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

*(Optional configuration)*:
- `DIARY_ENTRIES_DIR`: Path to your journal entries directory (defaults to `./entries`).
- `DIARY_DB_PATH`: Path to the SQLite database (defaults to `./diary.db`).

### 3. Add Entries

Place your journal entries in the `entries/` directory named using the `YYYY-MM-DD.md` format (e.g., `entries/2026-10-31.md`). Frontmatter `title` and `date` are supported but optional.

---

## Commands

### Synchronize Entries
Index new or modified journal entries into the local database:

```bash
diary sync
```

To specify a custom entries directory:
```bash
diary sync --dir /path/to/entries
```

### Query Your Archive
Ask a retrospective or thematic question:

```bash
# Shorthand syntax
diary "How did my reaction to high-stress situations evolve over time?"

# Explicit subcommand syntax
diary query "How did my reaction to high-stress situations evolve over time?"
```

Adjust the number of retrieved entries (default is 5):
```bash
diary "What were my key career realizations?" --limit 8
```

Query with a custom entries directory:
```bash
diary "How has my daily routine shifted?" --dir /path/to/entries
```
