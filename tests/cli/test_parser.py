"""Pure unit tests for CLI argument parsing, flags, and shorthands."""

from arc_life_diary.cli import build_parser, parse_cli_args


def test_cli_argument_parsing():
    # Sync command
    args_sync = parse_cli_args(["sync", "--dir", "./my_entries"])
    assert args_sync.command == "sync"
    assert args_sync.dir == "./my_entries"

    # Query command explicit
    args_query = parse_cli_args(["query", "stress response", "--limit", "3"])
    assert args_query.command == "query"
    assert args_query.query_text == "stress response"
    assert args_query.limit == 3

    # Query shorthand: diary "stress response"
    args_short = parse_cli_args(["stress response"])
    assert args_short.command == "query"
    assert args_short.query_text == "stress response"
    assert args_short.limit == 5

    # Search command explicit
    args_search = parse_cli_args(["search", "stress response", "--limit", "4", "--dir", "./entries"])
    assert args_search.command == "search"
    assert args_search.query_text == "stress response"
    assert args_search.limit == 4
    assert args_search.dir == "./entries"


def test_cli_help_parser():
    parser = build_parser()
    assert parser.prog == "diary"
