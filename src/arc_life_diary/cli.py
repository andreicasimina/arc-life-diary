"""Command-line interface for arc-life-diary.

Supports:
    diary sync [--dir <path>]
    diary "<query>" [--limit <int>] [--dir <path>]
"""

import argparse
from pathlib import Path
import sys
from typing import Optional

import dotenv

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

    return parser


def parse_cli_args(args=None):
    """Parses command line arguments, allowing diary "<query>" as shorthand."""
    raw_args = list(sys.argv[1:] if args is None else args)

    # Shorthand support: if first argument is not a known command or flag, treat as query
    if raw_args and not raw_args[0].startswith("-") and raw_args[0] not in ("sync", "query", "-h", "--help"):
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

    except ProviderAuthError as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        return 1
    except EmptyArchiveError as e:
        print(f"Empty Archive Warning: {e}", file=sys.stderr)
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
