"""Command-line interface for honeymoon weekend selection."""

from __future__ import annotations

import argparse
import os
import sys

from .candidates import generate_weekend_candidates
from .models import InputValidationError, load_input_from_json
from .optimizer import rank_weekends
from .reporting import (
    build_openai_narrative,
    build_result_payload,
    format_result_json,
    format_result_text,
)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build command-line parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="weekend-picker",
        description=(
            "Rank honeymoon weekend options under hard and soft constraints."
        ),
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input JSON file.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Return top N weekend options. Default: 3.",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format for deterministic result. Default: text.",
    )
    parser.add_argument(
        "--openai-api-key",
        default="",
        help=(
            "Optional OpenAI API key for narrative output. "
            "Default: read from OPENAI_API_KEY env var."
        ),
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model for narrative output. Default: gpt-4.1-mini.",
    )
    parser.add_argument(
        "--include-openai-narrative",
        action="store_true",
        help="Generate additional narrative text using OpenAI API.",
    )
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    """Run CLI flow.

    Args:
        argv (list[str] | None): Optional argument list. Defaults to None.

    Returns:
        int: Process exit code.
    """
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    if args.top_n <= 0:
        parser.error("--top-n must be greater than 0.")

    try:
        input_data = load_input_from_json(args.input)
        candidates = generate_weekend_candidates(
            min_date=input_data.min_date,
            max_date=input_data.max_date,
        )
        ranked = rank_weekends(
            input_data=input_data,
            candidates=candidates,
            top_n=args.top_n,
        )
        payload = build_result_payload(input_data=input_data, ranked_results=ranked)
    except InputValidationError as exc:
        print(f"Input validation error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return 1

    if args.output_format == "json":
        print(format_result_json(payload))
    else:
        print(format_result_text(payload))

    if args.include_openai_narrative:
        api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            print(
                "OpenAI narrative requested but no API key was provided.",
                file=sys.stderr,
            )
            return 2
        try:
            narrative = build_openai_narrative(
                payload=payload,
                api_key=api_key,
                model=args.model,
            )
        except RuntimeError as exc:
            print(f"OpenAI narrative error: {exc}", file=sys.stderr)
            return 1

        print("\nOpenAI Narrative:\n")
        print(narrative)

    return 0


def main() -> None:
    """Run the CLI and exit with its status code."""
    raise SystemExit(run_cli())
