"""Unit tests for the pure domain layer.

These tests need no DB, no FastAPI, no fixtures — proving that keeping
occupancy.py free of infrastructure imports actually pays off.
"""

import pytest

from occupancy import (
    NEAR_FULL_RATIO,
    OccupancyError,
    status_label,
    validate_event,
)


class TestValidateEvent:
    def test_in_on_empty_lot_is_allowed(self):
        validate_event(current=0, capacity=10, event_type="in")

    def test_in_below_capacity_is_allowed(self):
        validate_event(current=9, capacity=10, event_type="in")

    def test_out_when_occupied_is_allowed(self):
        validate_event(current=1, capacity=10, event_type="out")

    def test_in_on_full_lot_is_rejected(self):
        with pytest.raises(OccupancyError, match="full"):
            validate_event(current=10, capacity=10, event_type="in")

    def test_out_on_empty_lot_is_rejected(self):
        with pytest.raises(OccupancyError, match="empty"):
            validate_event(current=0, capacity=10, event_type="out")

    def test_unknown_event_type_is_rejected(self):
        with pytest.raises(OccupancyError, match="Unknown event type"):
            validate_event(current=5, capacity=10, event_type="fly")


class TestStatusLabel:
    @pytest.mark.parametrize(
        "current,capacity,expected",
        [
            (0, 20, "available"),
            (10, 20, "available"),
            (16, 20, "available"),  # 80% — below 85% threshold
            (17, 20, "near_full"),  # 85% — at threshold
            (19, 20, "near_full"),
            (20, 20, "full"),
            (21, 20, "full"),       # over capacity still reads as full
        ],
    )
    def test_thresholds(self, current, capacity, expected):
        assert status_label(current, capacity) == expected

    def test_near_full_threshold_is_85_percent(self):
        # Documents the constant so a future refactor doesn't silently shift it.
        assert NEAR_FULL_RATIO == 0.85
