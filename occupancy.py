"""Pure domain logic: validates events and labels lot status.

Kept free of DB and HTTP concerns so it can be reasoned about and tested in isolation.
"""

VALID_EVENT_TYPES = {"in", "out"}
NEAR_FULL_RATIO = 0.85


class OccupancyError(Exception):
    """Raised when an event would put a lot into an impossible state."""


def validate_event(*, current: int, capacity: int, event_type: str) -> None:
    if event_type not in VALID_EVENT_TYPES:
        raise OccupancyError(f"Unknown event type: {event_type!r}")
    if event_type == "in" and current >= capacity:
        raise OccupancyError("Lot is full")
    if event_type == "out" and current <= 0:
        raise OccupancyError("Lot is already empty")


def status_label(current: int, capacity: int) -> str:
    if current >= capacity:
        return "full"
    if current >= NEAR_FULL_RATIO * capacity:
        return "near_full"
    return "available"
