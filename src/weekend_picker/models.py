"""Domain models and input validation for weekend picking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any


class InputValidationError(ValueError):
    """Represent a validation error in the input payload."""


@dataclass(frozen=True)
class DateConstraint:
    """Represent one date-based constraint.

    Attributes:
        kind (str): Constraint type, either "date" or "interval".
        date_value (date | None): Specific date for kind "date".
        start_date (date | None): Start date for kind "interval".
        end_date (date | None): End date for kind "interval".
    """

    kind: str
    date_value: date | None = None
    start_date: date | None = None
    end_date: date | None = None

    def overlaps_date(self, target_date: date) -> bool:
        """Check whether the constraint overlaps a specific date.

        Args:
            target_date (date): Date to check.

        Returns:
            bool: True when the date is covered by the constraint.
        """
        if self.kind == "date":
            return self.date_value == target_date

        if self.start_date is None or self.end_date is None:
            return False
        return self.start_date <= target_date <= self.end_date

    def describe(self) -> str:
        """Build a human-readable description for reporting.

        Returns:
            str: Human-readable description.
        """
        if self.kind == "date" and self.date_value is not None:
            return f"date:{self.date_value.isoformat()}"
        if self.start_date is None or self.end_date is None:
            return "interval:invalid"
        return (
            f"interval:{self.start_date.isoformat()}.."
            f"{self.end_date.isoformat()}"
        )


@dataclass(frozen=True)
class PersonConstraints:
    """Represent one person's hard and soft constraints.

    Attributes:
        name (str): Person identifier.
        hard_constraints (list[DateConstraint]): Strictly disallowed dates.
        soft_constraints (list[DateConstraint]): Preferably avoided dates.
    """

    name: str
    hard_constraints: list[DateConstraint]
    soft_constraints: list[DateConstraint]


@dataclass(frozen=True)
class InputData:
    """Represent full optimization input payload.

    Attributes:
        min_date (date): Inclusive minimum date.
        max_date (date): Inclusive maximum date.
        people (list[PersonConstraints]): List of participants.
    """

    min_date: date
    max_date: date
    people: list[PersonConstraints]


def parse_iso_date(raw_date: str, field_name: str) -> date:
    """Parse an ISO date string.

    Args:
        raw_date (str): Date value in YYYY-MM-DD format.
        field_name (str): Field path for error context.

    Returns:
        date: Parsed date.

    Raises:
        InputValidationError: If date is not valid ISO format.
    """
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise InputValidationError(
            f"Invalid date at '{field_name}': '{raw_date}'. "
            "Expected YYYY-MM-DD."
        ) from exc


def _validate_object_keys(
    payload: dict[str, Any],
    allowed_keys: set[str],
    object_name: str,
) -> None:
    """Validate object keys and reject unknown fields.

    Args:
        payload (dict[str, Any]): Object to validate.
        allowed_keys (set[str]): Allowed keys for this object.
        object_name (str): Object label for errors.
    """
    unknown = set(payload.keys()) - allowed_keys
    if unknown:
        unknown_joined = ", ".join(sorted(unknown))
        raise InputValidationError(
            f"Unknown field(s) in {object_name}: {unknown_joined}"
        )


def _parse_constraint(
    raw_constraint: dict[str, Any],
    constraint_path: str,
) -> DateConstraint:
    """Parse one date constraint object.

    Args:
        raw_constraint (dict[str, Any]): Raw constraint payload.
        constraint_path (str): Error path for context.

    Returns:
        DateConstraint: Parsed and validated constraint.
    """
    _validate_object_keys(
        payload=raw_constraint,
        allowed_keys={"type", "date", "start_date", "end_date"},
        object_name=constraint_path,
    )

    raw_type = raw_constraint.get("type")
    if raw_type not in {"date", "interval"}:
        raise InputValidationError(
            f"Invalid constraint type at '{constraint_path}.type': "
            f"{raw_type!r}. Expected 'date' or 'interval'."
        )

    if raw_type == "date":
        if "date" not in raw_constraint:
            raise InputValidationError(
                f"Missing '{constraint_path}.date' for date constraint."
            )
        parsed_date = parse_iso_date(
            str(raw_constraint["date"]),
            f"{constraint_path}.date",
        )
        return DateConstraint(kind="date", date_value=parsed_date)

    if "start_date" not in raw_constraint or "end_date" not in raw_constraint:
        raise InputValidationError(
            "Missing interval bounds at "
            f"'{constraint_path}.start_date'/'{constraint_path}.end_date'."
        )

    parsed_start = parse_iso_date(
        str(raw_constraint["start_date"]),
        f"{constraint_path}.start_date",
    )
    parsed_end = parse_iso_date(
        str(raw_constraint["end_date"]),
        f"{constraint_path}.end_date",
    )
    if parsed_start > parsed_end:
        raise InputValidationError(
            f"Invalid interval at '{constraint_path}': start_date is after "
            "end_date."
        )

    return DateConstraint(
        kind="interval",
        start_date=parsed_start,
        end_date=parsed_end,
    )


def _parse_constraint_list(
    raw_constraints: Any,
    list_path: str,
) -> list[DateConstraint]:
    """Parse and validate list of constraints.

    Args:
        raw_constraints (Any): Raw constraint list.
        list_path (str): Error path for context.

    Returns:
        list[DateConstraint]: Parsed constraints.
    """
    if raw_constraints is None:
        return []

    if not isinstance(raw_constraints, list):
        raise InputValidationError(f"Expected list at '{list_path}'.")

    parsed_constraints: list[DateConstraint] = []
    for index, raw_constraint in enumerate(raw_constraints):
        if not isinstance(raw_constraint, dict):
            raise InputValidationError(
                f"Expected object at '{list_path}[{index}]'."
            )
        parsed_constraints.append(
            _parse_constraint(raw_constraint, f"{list_path}[{index}]")
        )
    return parsed_constraints


def _parse_person(raw_person: dict[str, Any], person_index: int) -> PersonConstraints:
    """Parse one person payload.

    Args:
        raw_person (dict[str, Any]): Raw person object.
        person_index (int): Index in people list.

    Returns:
        PersonConstraints: Parsed person.
    """
    person_path = f"people[{person_index}]"
    _validate_object_keys(
        payload=raw_person,
        allowed_keys={"name", "hard_constraints", "soft_constraints"},
        object_name=person_path,
    )

    raw_name = raw_person.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise InputValidationError(
            f"Expected non-empty string at '{person_path}.name'."
        )

    hard_constraints = _parse_constraint_list(
        raw_person.get("hard_constraints", []),
        f"{person_path}.hard_constraints",
    )
    soft_constraints = _parse_constraint_list(
        raw_person.get("soft_constraints", []),
        f"{person_path}.soft_constraints",
    )

    return PersonConstraints(
        name=raw_name.strip(),
        hard_constraints=hard_constraints,
        soft_constraints=soft_constraints,
    )


def parse_input_payload(payload: dict[str, Any]) -> InputData:
    """Parse and validate the full JSON input payload.

    Args:
        payload (dict[str, Any]): Raw payload dictionary.

    Returns:
        InputData: Parsed and validated input data.
    """
    _validate_object_keys(
        payload=payload,
        allowed_keys={"min_date", "max_date", "people"},
        object_name="root payload",
    )

    if "min_date" not in payload or "max_date" not in payload:
        raise InputValidationError("Both 'min_date' and 'max_date' are required.")

    min_date = parse_iso_date(str(payload["min_date"]), "min_date")
    max_date = parse_iso_date(str(payload["max_date"]), "max_date")
    if min_date > max_date:
        raise InputValidationError("Invalid range: min_date is after max_date.")

    raw_people = payload.get("people")
    if not isinstance(raw_people, list):
        raise InputValidationError("Expected list at 'people'.")
    if not raw_people:
        raise InputValidationError("Expected at least one person in 'people'.")

    people: list[PersonConstraints] = []
    seen_names: set[str] = set()
    for index, raw_person in enumerate(raw_people):
        if not isinstance(raw_person, dict):
            raise InputValidationError(f"Expected object at 'people[{index}]'.")
        parsed_person = _parse_person(raw_person, index)
        if parsed_person.name in seen_names:
            raise InputValidationError(
                f"Duplicate person name found: '{parsed_person.name}'."
            )
        seen_names.add(parsed_person.name)
        people.append(parsed_person)

    return InputData(min_date=min_date, max_date=max_date, people=people)


def load_input_from_json(file_path: str) -> InputData:
    """Load and validate JSON input data from a file.

    Args:
        file_path (str): Absolute or relative path to input JSON file.

    Returns:
        InputData: Parsed and validated input data.
    """
    json_path = Path(file_path)
    if not json_path.exists():
        raise InputValidationError(f"Input file does not exist: {file_path}")

    try:
        raw_content = json_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputValidationError(
            f"Failed to read input file '{file_path}': {exc}"
        ) from exc

    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise InputValidationError(
            f"Invalid JSON in '{file_path}': {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise InputValidationError("Root JSON value must be an object.")

    return parse_input_payload(payload)
