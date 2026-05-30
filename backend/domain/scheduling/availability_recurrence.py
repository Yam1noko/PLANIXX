from datetime import datetime, timedelta

from backend.models.scheduling import TimeWindow


_STATIC_RECURRENCE_RULES = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
}
_CUSTOM_RULE_PREFIXES = ("custom:", "interval:")


def normalize_availability_recurrence_rule(rule: str | None) -> str | None:
    if rule is None:
        return None

    normalized = rule.strip().lower()
    if not normalized:
        return None

    if normalized in _STATIC_RECURRENCE_RULES:
        return normalized

    for prefix in _CUSTOM_RULE_PREFIXES:
        if not normalized.startswith(prefix):
            continue

        days_part = normalized.split(":", maxsplit=1)[1].strip()
        if not days_part.isdigit() or int(days_part) <= 0:
            break

        return f"custom:{int(days_part)}"

    raise ValueError(
        "recurrence_rule must be one of: daily, weekly, biweekly, custom:<days>."
    )


def expand_availability_window(
    *,
    start: datetime,
    end: datetime,
    planning_start: datetime,
    planning_end: datetime,
    is_recurring: bool,
    recurrence_rule: str | None,
) -> list[TimeWindow]:
    if not is_recurring:
        clipped = _clip_window(start, end, planning_start, planning_end)
        return [clipped] if clipped else []

    normalized_rule = normalize_availability_recurrence_rule(recurrence_rule)
    if normalized_rule is None:
        raise ValueError("recurrence_rule is required when is_recurring=true")

    interval_days = _get_recurrence_interval_days(normalized_rule)
    interval = timedelta(days=interval_days)

    occurrence_start = start
    occurrence_end = end
    if occurrence_end <= planning_start:
        delta = planning_start - occurrence_end
        steps = int(delta // interval) + 1
        occurrence_start += interval * steps
        occurrence_end += interval * steps

    occurrences: list[TimeWindow] = []
    while occurrence_start < planning_end:
        clipped = _clip_window(
            occurrence_start,
            occurrence_end,
            planning_start,
            planning_end,
        )
        if clipped is not None:
            occurrences.append(clipped)

        occurrence_start += interval
        occurrence_end += interval

    return occurrences


def _get_recurrence_interval_days(rule: str) -> int:
    if rule in _STATIC_RECURRENCE_RULES:
        return _STATIC_RECURRENCE_RULES[rule]

    return int(rule.split(":", maxsplit=1)[1])


def _clip_window(
    start: datetime,
    end: datetime,
    planning_start: datetime,
    planning_end: datetime,
) -> TimeWindow | None:
    clipped_start = max(start, planning_start)
    clipped_end = min(end, planning_end)
    if clipped_end <= clipped_start:
        return None

    return TimeWindow(start=clipped_start, end=clipped_end)
