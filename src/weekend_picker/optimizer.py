"""Optimization and ranking logic for weekend selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .candidates import WeekendCandidate
from .models import DateConstraint, InputData, PersonConstraints


@dataclass(frozen=True)
class PersonSoftImpact:
    """Represent one person's soft-impact details for a weekend.

    Attributes:
        person_name (str): Person name.
        overlapped_dates (list[date]): Weekend dates overlapped by soft constraints.
        matched_constraints (list[str]): Human-readable matched soft constraints.
    """

    person_name: str
    overlapped_dates: list[date]
    matched_constraints: list[str]


@dataclass(frozen=True)
class PersonHardImpact:
    """Represent one person's hard-impact details for a weekend.

    Attributes:
        person_name (str): Person name.
        overlapped_dates (list[date]): Weekend dates overlapped by hard constraints.
        matched_constraints (list[str]): Human-readable matched hard constraints.
    """

    person_name: str
    overlapped_dates: list[date]
    matched_constraints: list[str]


@dataclass(frozen=True)
class WeekendEvaluation:
    """Represent scoring details for one valid weekend.

    Attributes:
        weekend (WeekendCandidate): Candidate weekend.
        selection_mode (str): Ranking mode, either "strict_hard" or "fallback_hard".
        hard_affected_people_count (int): Count of people affected by hard overlaps.
        fully_feasible_people_count (int): Count of people with zero soft overlap.
        affected_people_count (int): Count of people with at least one soft overlap.
        total_soft_overlap_days (int): Total soft-overlapped weekend days.
        affected_people (list[PersonSoftImpact]): Impact details by person.
        hard_affected_people (list[PersonHardImpact]): Hard-impact details by person.
    """

    weekend: WeekendCandidate
    selection_mode: str
    hard_affected_people_count: int
    fully_feasible_people_count: int
    affected_people_count: int
    total_soft_overlap_days: int
    affected_people: list[PersonSoftImpact]
    hard_affected_people: list[PersonHardImpact]


def _constraint_overlaps_any_weekend_day(
    constraint: DateConstraint,
    weekend_days: tuple[date, date, date],
) -> bool:
    """Check whether a constraint overlaps any day of a weekend.

    Args:
        constraint (DateConstraint): Constraint to evaluate.
        weekend_days (tuple[date, date, date]): Friday-Saturday-Sunday days.

    Returns:
        bool: True when at least one weekend day overlaps.
    """
    return any(constraint.overlaps_date(day) for day in weekend_days)


def _evaluate_person_hard_impact(
    person: PersonConstraints,
    weekend_days: tuple[date, date, date],
) -> PersonHardImpact | None:
    """Evaluate one person's hard overlap details for a weekend.

    Args:
        person (PersonConstraints): Person constraints.
        weekend_days (tuple[date, date, date]): Friday-Saturday-Sunday days.

    Returns:
        PersonHardImpact | None: Hard impact details if affected, else None.
    """
    overlapped_dates: set[date] = set()
    matched_constraints: list[str] = []
    for constraint in person.hard_constraints:
        matched_days = [day for day in weekend_days if constraint.overlaps_date(day)]
        if matched_days:
            overlapped_dates.update(matched_days)
            matched_constraints.append(constraint.describe())

    if not overlapped_dates:
        return None

    return PersonHardImpact(
        person_name=person.name,
        overlapped_dates=sorted(overlapped_dates),
        matched_constraints=matched_constraints,
    )


def _evaluate_person_soft_impact(
    person: PersonConstraints,
    weekend_days: tuple[date, date, date],
) -> PersonSoftImpact | None:
    """Evaluate one person's soft overlap details for a weekend.

    Args:
        person (PersonConstraints): Person constraints.
        weekend_days (tuple[date, date, date]): Friday-Saturday-Sunday days.

    Returns:
        PersonSoftImpact | None: Soft impact details if affected, else None.
    """
    overlapped_dates: set[date] = set()
    matched_constraints: list[str] = []
    for constraint in person.soft_constraints:
        matched_days = [day for day in weekend_days if constraint.overlaps_date(day)]
        if matched_days:
            overlapped_dates.update(matched_days)
            matched_constraints.append(constraint.describe())

    if not overlapped_dates:
        return None

    return PersonSoftImpact(
        person_name=person.name,
        overlapped_dates=sorted(overlapped_dates),
        matched_constraints=matched_constraints,
    )


def _evaluate_weekend_relaxed(
    input_data: InputData,
    weekend: WeekendCandidate,
) -> WeekendEvaluation:
    """Evaluate one candidate weekend allowing hard overlaps.

    Args:
        input_data (InputData): Parsed input data.
        weekend (WeekendCandidate): Candidate weekend.

    Returns:
        WeekendEvaluation: Evaluation result including hard and soft impacts.
    """
    hard_affected_people: list[PersonHardImpact] = []
    for person in input_data.people:
        hard_impact = _evaluate_person_hard_impact(person, weekend.days)
        if hard_impact is not None:
            hard_affected_people.append(hard_impact)

    affected_people: list[PersonSoftImpact] = []
    for person in input_data.people:
        impact = _evaluate_person_soft_impact(person, weekend.days)
        if impact is not None:
            affected_people.append(impact)

    affected_people_count = len(affected_people)
    fully_feasible_count = len(input_data.people) - affected_people_count
    hard_affected_people_count = len(hard_affected_people)
    total_soft_overlap_days = sum(
        len(person_impact.overlapped_dates) for person_impact in affected_people
    )

    return WeekendEvaluation(
        weekend=weekend,
        selection_mode="fallback_hard",
        hard_affected_people_count=hard_affected_people_count,
        fully_feasible_people_count=fully_feasible_count,
        affected_people_count=affected_people_count,
        total_soft_overlap_days=total_soft_overlap_days,
        affected_people=affected_people,
        hard_affected_people=hard_affected_people,
    )


def evaluate_weekend(
    input_data: InputData,
    weekend: WeekendCandidate,
) -> WeekendEvaluation | None:
    """Evaluate one candidate weekend with strict hard constraints.

    Args:
        input_data (InputData): Parsed input data.
        weekend (WeekendCandidate): Candidate weekend.

    Returns:
        WeekendEvaluation | None: Evaluation result if hard constraints pass.
    """
    evaluation = _evaluate_weekend_relaxed(input_data, weekend)
    if evaluation.hard_affected_people_count > 0:
        return None

    return WeekendEvaluation(
        weekend=evaluation.weekend,
        selection_mode="strict_hard",
        hard_affected_people_count=0,
        fully_feasible_people_count=evaluation.fully_feasible_people_count,
        affected_people_count=evaluation.affected_people_count,
        total_soft_overlap_days=evaluation.total_soft_overlap_days,
        affected_people=evaluation.affected_people,
        hard_affected_people=[],
    )


def rank_weekends(
    input_data: InputData,
    candidates: list[WeekendCandidate],
    top_n: int = 3,
) -> list[WeekendEvaluation]:
    """Rank valid weekends according to the optimization objective.

    Args:
        input_data (InputData): Parsed input data.
        candidates (list[WeekendCandidate]): Candidate weekends.
        top_n (int): Number of top items to return. Defaults to 3.

    Returns:
        list[WeekendEvaluation]: Ranked weekend evaluations.
    """
    if top_n <= 0:
        return []

    strict_evaluations = [
        evaluation
        for candidate in candidates
        if (evaluation := evaluate_weekend(input_data, candidate)) is not None
    ]

    strict_evaluations.sort(
        key=lambda item: (
            -item.fully_feasible_people_count,
            item.affected_people_count,
            item.total_soft_overlap_days,
            item.weekend.start_date,
        )
    )
    if strict_evaluations:
        return strict_evaluations[:top_n]

    relaxed_evaluations = [
        _evaluate_weekend_relaxed(input_data, candidate) for candidate in candidates
    ]
    relaxed_evaluations.sort(
        key=lambda item: (
            item.hard_affected_people_count,
            item.affected_people_count,
            item.total_soft_overlap_days,
            item.weekend.start_date,
        )
    )
    return relaxed_evaluations[:top_n]
