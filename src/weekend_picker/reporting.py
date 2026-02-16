"""Reporting utilities for weekend ranking output."""

from __future__ import annotations

from datetime import date
import json
from typing import Any

from .models import InputData
from .optimizer import WeekendEvaluation


def _to_iso(value: date) -> str:
    """Convert date value to ISO string.

    Args:
        value (date): Date to convert.

    Returns:
        str: Date in YYYY-MM-DD format.
    """
    return value.isoformat()


def build_result_payload(
    input_data: InputData,
    ranked_results: list[WeekendEvaluation],
) -> dict[str, Any]:
    """Build structured deterministic output payload.

    Args:
        input_data (InputData): Parsed input data.
        ranked_results (list[WeekendEvaluation]): Ranked weekend results.

    Returns:
        dict[str, Any]: JSON-serializable result payload.
    """
    options: list[dict[str, Any]] = []
    for index, result in enumerate(ranked_results, start=1):
        affected_people = []
        for impact in result.affected_people:
            affected_people.append(
                {
                    "name": impact.person_name,
                    "overlapped_dates": [
                        _to_iso(day) for day in impact.overlapped_dates
                    ],
                    "matched_soft_constraints": impact.matched_constraints,
                }
            )

        options.append(
            {
                "rank": index,
                "selection_mode": result.selection_mode,
                "weekend": {
                    "start_date": _to_iso(result.weekend.start_date),
                    "end_date": _to_iso(result.weekend.end_date),
                    "days": [_to_iso(day) for day in result.weekend.days],
                },
                "score": {
                    "hard_affected_people_count": result.hard_affected_people_count,
                    "fully_feasible_people_count": (
                        result.fully_feasible_people_count
                    ),
                    "affected_people_count": result.affected_people_count,
                    "total_soft_overlap_days": result.total_soft_overlap_days,
                },
                "hard_affected_people": [
                    {
                        "name": impact.person_name,
                        "overlapped_dates": [
                            _to_iso(day) for day in impact.overlapped_dates
                        ],
                        "matched_hard_constraints": impact.matched_constraints,
                    }
                    for impact in result.hard_affected_people
                ],
                "affected_people": affected_people,
            }
        )

    return {
        "search_window": {
            "min_date": _to_iso(input_data.min_date),
            "max_date": _to_iso(input_data.max_date),
        },
        "participant_count": len(input_data.people),
        "options": options,
    }


def format_result_text(payload: dict[str, Any]) -> str:
    """Format deterministic payload as human-readable text.

    Args:
        payload (dict[str, Any]): Structured result payload.

    Returns:
        str: Plain-text report.
    """
    lines: list[str] = []
    window = payload["search_window"]
    lines.append(
        "Search window: "
        f"{window['min_date']} to {window['max_date']} "
        f"({payload['participant_count']} participants)"
    )
    lines.append("")

    options = payload.get("options", [])
    if not options:
        lines.append("No weekend candidates available in the selected date window.")
        return "\n".join(lines)

    top_mode = options[0]["selection_mode"]
    if top_mode == "fallback_hard":
        lines.append(
            "Fallback mode enabled: no weekend satisfied all hard constraints. "
            "Ranking now minimizes people affected by hard constraints first."
        )
        lines.append("")

    lines.append("Top weekend options:")
    for option in options:
        weekend = option["weekend"]
        score = option["score"]
        lines.append(
            f"- #{option['rank']} {weekend['start_date']} -> "
            f"{weekend['end_date']}: "
            f"hard_affected_people={score['hard_affected_people_count']}, "
            f"fully_feasible={score['fully_feasible_people_count']}, "
            f"affected_people={score['affected_people_count']}, "
            f"soft_overlap_days={score['total_soft_overlap_days']}"
        )

        hard_affected = option["hard_affected_people"]
        if hard_affected:
            lines.append("  hard_affected_people:")
            for person in hard_affected:
                matched_hard = ", ".join(person["matched_hard_constraints"])
                hard_dates = ", ".join(person["overlapped_dates"])
                lines.append(
                    f"  - {person['name']}: dates=[{hard_dates}] "
                    f"constraints=[{matched_hard}]"
                )
        else:
            lines.append("  hard_affected_people: none")

        affected = option["affected_people"]
        if not affected:
            lines.append("  affected_people: none")
            continue

        lines.append("  affected_people:")
        for person in affected:
            matched = ", ".join(person["matched_soft_constraints"])
            dates = ", ".join(person["overlapped_dates"])
            lines.append(
                f"  - {person['name']}: dates=[{dates}] "
                f"constraints=[{matched}]"
            )

    return "\n".join(lines)


def format_result_json(payload: dict[str, Any], indent: int = 2) -> str:
    """Format deterministic payload as pretty JSON.

    Args:
        payload (dict[str, Any]): Structured result payload.
        indent (int): JSON indentation. Defaults to 2.

    Returns:
        str: JSON string.
    """
    return json.dumps(payload, indent=indent, ensure_ascii=True)


def build_openai_narrative(
    payload: dict[str, Any],
    api_key: str,
    model: str = "gpt-4.1-mini",
) -> str:
    """Generate optional narrative from deterministic output via OpenAI.

    Args:
        payload (dict[str, Any]): Structured deterministic payload.
        api_key (str): OpenAI API key.
        model (str): OpenAI model name. Defaults to gpt-4.1-mini.

    Returns:
        str: Narrative text generated by the OpenAI API.

    Raises:
        RuntimeError: If OpenAI package is missing or API call fails.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI narrative requested but 'openai' package is not installed."
        ) from exc

    try:
        client = OpenAI(api_key=api_key)
        completion = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a planning assistant. "
                        "Summarize weekend options concisely and objectively. "
                        "Always write in European Portuguese (Portugues de "
                        "Portugal, pt-PT), using natural phrasing for Portugal."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Using this deterministic ranking payload, produce a short "
                        "structured summary with sections: Best Option, Why, and "
                        "People Potentially Affected. Output must be in "
                        "European Portuguese (pt-PT).\n\n"
                        f"{json.dumps(payload, ensure_ascii=True)}"
                    ),
                },
            ],
        )
    except Exception as exc:  # pragma: no cover - external API behavior
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    text = completion.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI request succeeded but returned empty text.")
    return text
