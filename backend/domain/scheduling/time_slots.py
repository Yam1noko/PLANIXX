from datetime import datetime, timedelta
from math import ceil

from backend.models.scheduling import TimeWindow


def round_up_to_slots(duration_minutes: int, slot_minutes: int) -> int:
    return ceil(duration_minutes / slot_minutes)


def datetime_to_slot(
    value: datetime,
    planning_start: datetime,
    slot_minutes: int,
) -> int:
    delta_minutes = (value - planning_start).total_seconds() / 60
    return ceil(delta_minutes / slot_minutes)


def datetime_to_slot_floor(
    value: datetime,
    planning_start: datetime,
    slot_minutes: int,
) -> int:
    delta_minutes = (value - planning_start).total_seconds() / 60
    return int(delta_minutes // slot_minutes)


def slot_to_datetime(
    slot: int,
    planning_start: datetime,
    slot_minutes: int,
) -> datetime:
    return planning_start + timedelta(minutes=slot * slot_minutes)


def interval_overlaps(
    start_slot: int,
    duration_slots: int,
    busy_start: int,
    busy_end: int,
) -> bool:
    end_slot = start_slot + duration_slots
    return start_slot < busy_end and end_slot > busy_start


def interval_inside_window(
    start: datetime,
    end: datetime,
    window: TimeWindow,
) -> bool:
    return start >= window.start and end <= window.end


def interval_inside_any_window(
    start: datetime,
    end: datetime,
    windows: list[TimeWindow],
) -> bool:
    return any(interval_inside_window(start, end, window) for window in windows)


def interval_overlaps_any_window(
    start: datetime,
    end: datetime,
    windows: list[TimeWindow],
) -> bool:
    return any(start < window.end and end > window.start for window in windows)
