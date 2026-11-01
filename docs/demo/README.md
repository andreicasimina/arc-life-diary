# Demo & Showcase Recording Tools

This directory contains the cassettes, seed data, and automation scripts used to record terminal demonstration GIFs for **arc-life-diary**.

---

## Prerequisites

GIF generation requires **[VHS](https://github.com/charmbracelet/vhs)** by Charmbracelet (which also requires `ttyd` and `ffmpeg`).

For setup instructions across all platforms, see the **[VHS Installation Guide](https://github.com/charmbracelet/vhs#installation)**.

---

## Directory Contents

| File | Description |
| :--- | :--- |
| [`seed_demo_entries.py`](seed_demo_entries.py) | Generates non-personal, synthetic journal entries (2024–2026) in `entries/` for clean demonstrations. |
| [`core_lifecycle.tape`](core_lifecycle.tape) | VHS cassette recording: new entry creation, incremental `diary sync`, and temporal synthesis (`diary "<query>"`). |
| [`backup_restore.tape`](backup_restore.tape) | VHS cassette recording: entry listing, encrypted cloud backup (`diary backup`), simulated loss, and recovery (`diary restore --latest`). |
| [`generate_demos.sh`](generate_demos.sh) | Automated bash script to seed, sync, and record all cassettes in one pass. |

Rendered GIFs are placed in [`docs/assets/`](../assets/):
- `docs/assets/core-lifecycle.gif`
- `docs/assets/backup-restore.gif`

---

## How to Run

Ensure your virtual environment is active and dependencies are installed from the repository root:
```bash
source .venv/bin/activate
pip install -e .
```

### Option 1: Automated Run (All Demos)

Run the included runner from the repository root:
```bash
./docs/demo/generate_demos.sh
```

### Option 2: Step-by-Step Manual Recording

#### 1. Seed Demo Entries & Initial Sync
Populate 4 synthetic journal entries and prime the local SQLite vector database:
```bash
python3 docs/demo/seed_demo_entries.py
diary sync
```

#### 2. Record Core Lifecycle Showcase
Generates `docs/assets/core-lifecycle.gif`:
```bash
# Ensure any temporary 2026-11-01.md entry is cleared before recording
rm -f entries/2026-11-01.md
diary sync

vhs docs/demo/core_lifecycle.tape
```

#### 3. Record Disaster Recovery Showcase
Generates `docs/assets/backup-restore.gif`:
```bash
vhs docs/demo/backup_restore.tape
```

---

## Configuration & Privacy Notes

- **API Keys**: Ensure `GEMINI_API_KEY` is configured in `.env` for the synthesis query to succeed.
- **Google Drive Isolation**: Set `GDRIVE_FOLDER_ID` in `.env` to a dedicated test folder to keep demonstration backups separate from production data.
- **Privacy First**: Always run `python3 docs/demo/seed_demo_entries.py` on a test vault before recording to prevent accidental exposure of personal journals.
