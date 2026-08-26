"""Tests for MCP result extraction."""

from custom_components.sparkyfitness.extract import (
    parse_checkin_diary,
    parse_exercise_search,
    parse_fasting_status,
    parse_health_summary,
    parse_logging_streak,
)


def test_parse_structured_summary_and_streak() -> None:
    """JSON embedded below an MCP heading is projected without guessing."""

    summary = parse_health_summary(
        '# Health Summary\n\n{"nutrition":{"total_calories":1800,"avg_protein":120.5,"avg_carbs":200,"avg_fat":60},'
        '"fitness":{"workout_count":2},"vitals":{"latest_weight":{"weight":84.7,"date":"2026-08-26"}},'
        '"hydration":{"total_water_ml":2500}}'
    )
    assert summary == {
        "calories_today": 1800,
        "protein_today": 120.5,
        "carbs_today": 200,
        "fat_today": 60,
        "water_today": 2500,
        "exercise_count_today": 2,
        "weight": 84.7,
        "weight_unit": "kg",
    }
    assert parse_logging_streak('{"current_streak":9,"last_logged":"2026-08-26"}') == 9


def test_parse_checkin_markdown() -> None:
    """The current upstream Markdown contract yields priority sensor fields."""

    result = parse_checkin_diary(
        """### Check-in Diary: today

#### Biometrics
- **Weight:** 180.2 lbs
- **Steps:** 12345
- **Body Fat:** 18.4%

## Mood
- 8/10 — Great

## Sleep
- 7h 30m | score: 91/100 | (manual)
"""
    )
    assert result == {
        "weight": 180.2,
        "weight_unit": "lbs",
        "steps_today": 12345,
        "body_fat": 18.4,
        "mood": 8.0,
        "sleep_duration": 7.5,
        "sleep_score": 91.0,
    }


def test_parse_fasting_and_exercise_search() -> None:
    """Active fast metadata and exact exercise candidates stay compact."""

    assert parse_fasting_status("No active fasting session.") is None
    assert parse_fasting_status(
        '# Fasting Status\n\n{"start_time":"2026-08-26T18:00:00Z","end_time":null,'
        '"fasting_status":"ACTIVE","fasting_type":"16:8","user_id":"secret"}'
    ) == {
        "start_time": "2026-08-26T18:00:00Z",
        "end_time": None,
        "fasting_status": "ACTIVE",
        "fasting_type": "16:8",
    }
    assert parse_exercise_search(
        "**Bench Press** (Strength)\n  Muscles: Chest | Equipment: Barbell\n"
        "  ID: 11111111-1111-1111-1111-111111111111"
    ) == [
        {
            "name": "Bench Press",
            "id": "11111111-1111-1111-1111-111111111111",
        }
    ]
