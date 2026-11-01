#!/usr/bin/env bash
set -euo pipefail

# Script to regenerate demo GIFs from repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

echo "==> Seeding initial demo entries..."
python3 docs/demo/seed_demo_entries.py

echo "==> Syncing vector store with seed entries..."
diary sync

echo "==> Recording Core Lifecycle demo..."
vhs docs/demo/core_lifecycle.tape

echo "==> Recording Backup & Restore demo..."
vhs docs/demo/backup_restore.tape

echo "==> Demos successfully generated in docs/assets/!"
