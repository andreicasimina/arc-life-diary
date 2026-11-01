# arc-life-diary

A command-line introspection tool for personal journals. It semantically searches through markdown journal entries across multiple languages and synthesizes developmental reflections tracing how thoughts, perspectives, and coping mechanisms have evolved over time.

---

## What It Can Do

- **Cross-Lingual Semantic Search**: Query and retrieve relevant entries across multiple languages and mixed-language notes.
- **Temporal & Developmental Synthesis**: Synthesizes a coherent chronological narrative tracing behavioral and mindset shifts across years of entries.
- **Auditable Citations**: Lists the source journal entries for your query with dates, optional titles, and vector similarity metrics.
- **Fast, Local Vector Storage**: Uses local SQLite vector storage (`sqlite-vec`) with incremental caching so unchanged entries are not re-embedded.

![Core Lifecycle Demo](docs/assets/core-lifecycle.gif)

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

Place your journal entries in the `entries/` directory named using the `YYYY-MM-DD.md` format (e.g., `entries/2026-01-15.md`). Frontmatter `title` and `date` are supported but optional.

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

### Semantic Search
Retrieve matching entries with similarity distance scores without LLM synthesis:

```bash
diary search "work-life balance"
```

Adjust the number of retrieved entries:
```bash
diary search "project takeaways" --limit 8
```

Search with a custom entries directory:
```bash
diary search "daily workflow" --dir /path/to/entries
```

### Query Your Archive
Ask a retrospective or thematic question:

```bash
# Shorthand syntax
diary "How have my perspectives on work-life balance evolved?"

# Explicit subcommand syntax
diary query "How have my perspectives on work-life balance evolved?"
```

Adjust the number of retrieved entries (default is 5):
```bash
diary "What were my key project takeaways?" --limit 8
```

Query with a custom entries directory:
```bash
diary "How has my daily workflow shifted?" --dir /path/to/entries
```

### Encrypted Cloud Backup & Restore

Safely package and encrypt entries using AES-256 (with encrypted headers via `py7zr`) and synchronize with Google Drive for tamper-proof disaster recovery:

![Backup and Restore Demo](docs/assets/backup-restore.gif)

#### Backup
Safely package and encrypt entries using AES-256 (with encrypted headers via `py7zr`) and upload to Google Drive:

```bash
diary backup
```
You will be interactively prompted to enter and confirm an encryption password. Passwords are never stored on disk.

To back up a custom entries directory:
```bash
diary backup --dir /path/to/entries
```

#### Restore
Restore entries from an encrypted Google Drive archive:

```bash
# Interactively choose from available backups
diary restore

# Automatically restore the latest backup
diary restore --latest

# Restore a specific backup file by its Google Drive file ID
diary restore --file-id <drive-file-id>
```
During restore, the CLI prompts for your decryption password and warns before overwriting any existing local files. After restoring, run `diary sync` to update the local vector index.
