"""Tests for local fasting projections."""

from datetime import UTC, datetime

from custom_components.sparkyfitness.fasting import fasting_metrics


def test_parseable_protocol_projects_progress_and_target() -> None:
    """A 16:8 label supplies a deterministic 16-hour fasting target."""

    result = fasting_metrics(
        {
            "start_time": "2026-08-26T00:00:00Z",
            "fasting_status": "ACTIVE",
            "fasting_type": "16:8",
        },
        now=datetime(2026, 8, 26, 8, tzinfo=UTC),
    )
    assert result == {
        "elapsed_seconds": 28800,
        "target_end": datetime(2026, 8, 26, 16, tzinfo=UTC),
        "remaining_seconds": 28800,
        "progress": 50.0,
        "goal_reached": False,
    }


def test_unknown_protocol_keeps_only_observed_elapsed_time() -> None:
    """Free-form labels do not produce an invented target duration."""

    result = fasting_metrics(
        {
            "start_time": "2026-08-26T00:00:00Z",
            "fasting_status": "ACTIVE",
            "fasting_type": "Intermittent",
        },
        now=datetime(2026, 8, 26, 1, tzinfo=UTC),
    )
    assert result == {"elapsed_seconds": 3600}
