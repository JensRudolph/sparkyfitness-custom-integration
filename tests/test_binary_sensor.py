"""Tests for dynamic and partial-failure binary sensor behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.sparkyfitness.binary_sensor import (
    SparkyFitnessHabitBinarySensor,
)
from custom_components.sparkyfitness.models import SparkyFitnessData

HABIT_ID = "11111111-1111-1111-1111-111111111111"


def _coordinator(habit: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.config_entry = SimpleNamespace(
        entry_id="entry-1",
        options={},
        data={},
    )
    coordinator.client.server_version = "1.6.3"
    coordinator.client.endpoint = "https://sparky.example.com/mcp"
    coordinator.last_update_success = True
    coordinator.data = SparkyFitnessData(habits={HABIT_ID: habit})
    return coordinator


def test_habit_name_updates_and_partial_history_is_unavailable() -> None:
    """Renames are live while failed history never appears as an off state."""

    coordinator = _coordinator(
        {
            "id": HABIT_ID,
            "name": "Walk",
            "completed": True,
            "history_available": True,
        }
    )
    entity = SparkyFitnessHabitBinarySensor(coordinator, HABIT_ID)
    assert entity.name == "Walk"
    assert entity.is_on is True
    assert entity.available is True

    coordinator.data.habits[HABIT_ID].update(
        {"name": "Morning walk", "history_available": False}
    )
    assert entity.name == "Morning walk"
    assert entity.is_on is True
    assert entity.available is False


def test_unlogged_habit_is_off_but_distinguishable_from_a_failed_poll() -> None:
    """A successful empty history is a valid not-completed state."""

    coordinator = _coordinator(
        {
            "id": HABIT_ID,
            "name": "Walk",
            "completed": None,
            "history_available": True,
        }
    )
    entity = SparkyFitnessHabitBinarySensor(coordinator, HABIT_ID)
    assert entity.is_on is False
    assert entity.extra_state_attributes == {
        "habit_id": HABIT_ID,
        "logged_today": False,
    }
