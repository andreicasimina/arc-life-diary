"""Command-line interface for arc-life-diary.

Supports:
    diary sync [--dir <path>]
    diary "<query>" [--limit <int>] [--dir <path>]
    diary search "<query>" [--limit <int>] [--dir <path>]
    diary backup [--dir <path>]
    diary restore [--dir <path>] [--latest] [--file-id <id>]
"""

import argparse
import getpass
from pathlib import Path
import sys
from typing import Optional

import dotenv

from arc_life_diary.backup import (
    BackupError,
    BackupService,
    DecryptionError,
    PasswordMismatchError,
    RestoreCancelledError,
)
from arc_life_diary.providers.gdrive import GoogleDriveAuthError, GoogleDriveStorage
from arc_life_diary.providers.gemini import GeminiEmbeddingModel, GeminiLLMClient, ProviderAuthError
from arc_life_diary.service import DiaryService, EmptyArchiveError
from arc_life_diary.store import DiaryStore, DimensionMismatchError


def load_config() -> dict:
    """Loads configuration strictly from repository .env file."""
    env_path = Path(".env")
    env_vars = dotenv.dotenv_values(env_path) if env_path.is_file() else {}
    return {
        "entries_dir": env_vars.get("DIARY_ENTRIES_DIR", "./entries"),
        "db_path": env_vars.get("DIARY_DB_PATH", "./diary.db"),
    }


def build_parser() -> argparse.ArgumentParser:
    """Constructs the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="diary",
        description="Personal archive introspection CLI with semantic search and temporal synthesis.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Subcommand: sync
    sync_parser = subparsers.add_parser("sync", help="Synchronize journal entries with vector index")
    sync_parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to entries directory (overrides DIARY_ENTRIES_DIR in .env)",
    )

    # Subcommand: query
    query_parser = subparsers.add_parser("query", help="Execute semantic query on journal entries")
    query_parser.add_argument("query_text", type=str, help="Search query string")
    query_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of relevant entries to retrieve (default: 5)",
    )
    query_parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to entries directory (overrides DIARY_ENTRIES_DIR in .env)",
    )

    # Subcommand: search
    search_parser = subparsers.add_parser("search", help="Execute semantic search on journal entries without synthesis")
    search_parser.add_argument("query_text", type=str, help="Search query string")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of relevant entries to retrieve (default: 5)",
    )
    search_parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to entries directory (overrides DIARY_ENTRIES_DIR in .env)",
    )

    # Subcommand: backup
    backup_parser = subparsers.add_parser("backup", help="Create an encrypted backup of journal entries on Google Drive")
    backup_parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to entries directory (overrides DIARY_ENTRIES_DIR in .env)",
    )

    # Subcommand: restore
    restore_parser = subparsers.add_parser("restore", help="Restore journal entries from an encrypted Google Drive backup")
    restore_parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Path to destination entries directory (overrides DIARY_ENTRIES_DIR in .env)",
    )
    restore_parser.add_argument(
        "--latest",
        action="store_true",
        help="Automatically restore the most recent backup without prompting for selection",
    )
    restore_parser.add_argument(
        "--file-id",
        type=str,
        default=None,
        help="Specific Google Drive file ID to restore",
    )

    return parser


def parse_cli_args(args=None):
    """Parses command line arguments, allowing diary "<query>" as shorthand."""
    raw_args = list(sys.argv[1:] if args is None else args)

    # Shorthand support: if first argument is not a known command or flag, treat as query
    if raw_args and not raw_args[0].startswith("-") and raw_args[0] not in ("sync", "query", "search", "backup", "restore", "-h", "--help"):
        # Re-format as query command
        raw_args = ["query"] + raw_args

    parser = build_parser()
    return parser.parse_args(raw_args)


def main(argv=None) -> int:
    """CLI entry point."""
    args = parse_cli_args(argv)
    if not args.command:
        parser = build_parser()
        parser.print_help()
        return 0

    config = load_config()
    entries_dir = Path(args.dir or config["entries_dir"])
    db_path = Path(config["db_path"])

    try:
        if args.command == "backup":
            password = getpass.getpass("Enter backup encryption password: ")
            if not password:
                print("Error: Password cannot be empty.", file=sys.stderr)
                return 1
            confirm = getpass.getpass("Confirm backup encryption password: ")
            if password != confirm:
                print("Error: Passwords do not match. Backup aborted.", file=sys.stderr)
                return 1

            storage = GoogleDriveStorage(env_path=".env")
            backup_service = BackupService(storage=storage)

            print("Packaging and encrypting entries...")
            metadata = backup_service.create_backup(
                entries_dir=entries_dir,
                password=password,
                confirm_password=confirm,
            )
            print(
                f"Backup uploaded successfully!\n"
                f"  Archive: {metadata.name}\n"
                f"  File ID: {metadata.file_id}\n"
                f"  Size:    {metadata.size_bytes} bytes"
            )
            return 0

        elif args.command == "restore":
            storage = GoogleDriveStorage(env_path=".env")
            backup_service = BackupService(storage=storage)

            print("Querying Google Drive for backups...")
            backups = backup_service.list_backups()
            if not backups:
                print("No backups found on Google Drive.", file=sys.stderr)
                return 0

            target_id = args.file_id
            if not target_id:
                if args.latest:
                    target_id = backups[0].file_id
                else:
                    print("Available backups:")
                    for idx, b in enumerate(backups, 1):
                        dt_str = b.created_at.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"  [{idx}] {b.name} ({b.size_bytes} bytes, {dt_str})")
                    try:
                        choice = input(f"Select backup to restore [1-{len(backups)}] (default 1): ").strip()
                        selected_idx = int(choice) if choice else 1
                        if not (1 <= selected_idx <= len(backups)):
                            print(f"Invalid selection: {choice}", file=sys.stderr)
                            return 1
                        target_id = backups[selected_idx - 1].file_id
                    except ValueError:
                        print(f"Invalid numeric selection: {choice}", file=sys.stderr)
                        return 1
                    except (EOFError, KeyboardInterrupt):
                        print("\nRestore cancelled.", file=sys.stderr)
                        return 1

            password = getpass.getpass("Enter backup decryption password: ")
            if not password:
                print("Error: Decryption password cannot be empty.", file=sys.stderr)
                return 1

            def confirm_overwrite(conflicts):
                print(f"Warning: {len(conflicts)} file(s) already exist in '{entries_dir}':")
                for c in conflicts[:5]:
                    print(f"  - {c}")
                if len(conflicts) > 5:
                    print(f"  ... and {len(conflicts) - 5} more")
                try:
                    ans = input("Overwrite existing local files? [y/N]: ").strip().lower()
                    return ans in ("y", "yes")
                except (EOFError, KeyboardInterrupt):
                    return False

            print("Downloading and restoring backup...")
            restored = backup_service.restore_backup(
                destination_dir=entries_dir,
                password=password,
                file_id=target_id,
                overwrite_confirm_fn=confirm_overwrite,
            )
            print(f"Successfully restored {len(restored)} entries to '{entries_dir}'.")
            print("Run 'diary sync' to rebuild the local vector index.")
            return 0

        # Provider configuration: to switch providers (e.g., to local Ollama, OpenAI, or Mock),
        # swap out GeminiEmbeddingModel and GeminiLLMClient below with the new provider classes.
        embedder = GeminiEmbeddingModel(env_path=".env")
        llm = GeminiLLMClient(env_path=".env")

        store = DiaryStore(db_path=db_path, dimensions=embedder.dimensions)
        service = DiaryService(store=store, embedder=embedder, llm=llm)

        if args.command == "sync":
            stats = service.sync(entries_dir)
            print(
                f"Sync complete: {stats.scanned} scanned, {stats.added} added, "
                f"{stats.updated} updated, {stats.deleted} deleted, {stats.unchanged} unchanged."
            )
            return 0

        elif args.command == "query":
            # Automatically sync if database has not been initialized with any entries
            if store.count_entries() == 0 and entries_dir.exists():
                print("First run detected. Synchronizing entries...")
                service.sync(entries_dir)

            output = service.query(args.query_text, limit=args.limit)
            print(output)
            return 0

        elif args.command == "search":
            # Automatically sync if database has not been initialized with any entries
            if store.count_entries() == 0 and entries_dir.exists():
                print("First run detected. Synchronizing entries...")
                service.sync(entries_dir)

            output = service.search(args.query_text, limit=args.limit)
            print(output)
            return 0

    except ProviderAuthError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        return 1
    except GoogleDriveAuthError as e:
        print(f"Google Drive Authentication Error: {e}", file=sys.stderr)
        return 1
    except DecryptionError as e:
        print(f"Decryption Error: {e}", file=sys.stderr)
        return 1
    except PasswordMismatchError as e:
        print(f"Password Mismatch: {e}", file=sys.stderr)
        return 1
    except RestoreCancelledError as e:
        print(f"Restore Cancelled: {e}", file=sys.stderr)
        return 1
    except EmptyArchiveError as e:
        print(f"Empty Archive Warning: {e}", file=sys.stderr)
        return 1
    except BackupError as e:
        print(f"Backup Error: {e}", file=sys.stderr)
        return 1
    except DimensionMismatchError as e:
        print(f"Dimension Mismatch: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
