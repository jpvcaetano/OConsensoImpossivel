"""Weekend candidate generation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class WeekendCandidate:
    """Represent one Friday-Sunday weekend candidate.

    Attributes:
        start_date (date): Friday date.
        end_date (date): Sunday date.
        days (tuple[date, date, date]): Ordered weekend days.
    """

    start_date: date
    end_date: date
    days: tuple[date, date, date]


def _first_friday_on_or_after(input_date: date) -> date:
    """Find the first Friday on or after input date.

    Args:
        input_date (date): Date used as lower bound.

    Returns:
        date: First Friday on or after the input date.
    """
    friday_weekday = 4
    day_offset = (friday_weekday - input_date.weekday()) % 7
    return input_date + timedelta(days=day_offset)


def generate_weekend_candidates(
    min_date: date,
    max_date: date,
) -> list[WeekendCandidate]:
    """Generate Friday-Sunday candidates inside inclusive date bounds.

    Args:
        min_date (date): Inclusive lower bound.
        max_date (date): Inclusive upper bound.

    Returns:
        list[WeekendCandidate]: Candidate weekends.
    """
    first_friday = _first_friday_on_or_after(min_date)
    candidates: list[WeekendCandidate] = []

    current_friday = first_friday
    while current_friday <= max_date:
        saturday = current_friday + timedelta(days=1)
        sunday = current_friday + timedelta(days=2)

        if sunday > max_date:
            break

        if current_friday >= min_date:
            candidates.append(
                WeekendCandidate(
                    start_date=current_friday,
                    end_date=sunday,
                    days=(current_friday, saturday, sunday),
                )
            )

        current_friday += timedelta(days=7)

    return candidates
