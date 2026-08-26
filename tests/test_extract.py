"""Tests for MCP result extraction."""

from custom_components.sparkyfitness.extract import (
    parse_30_day_trends,
    parse_checkin_diary,
    parse_exercise_search,
    parse_fasting_status,
    parse_goal_snapshot,
    parse_habit_completion,
    parse_habit_list,
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


def test_parse_goal_and_30_day_trend_json() -> None:
    """Structured goal and trend tools project only stable scalar values."""

    assert parse_goal_snapshot(
        '{"calories":2100,"protein":150,"carbs":220,"fat":70,'
        '"water_goal_ml":2500,"sodium":2000}'
    ) == {
        "calorie_goal": 2100,
        "protein_goal": 150,
        "carbs_goal": 220,
        "fat_goal": 70,
        "water_goal": 2500,
    }
    assert parse_30_day_trends(
        '{"period":{"days":30},"food":{"days_logged":28,'
        '"avg_daily_calories":1950,"avg_daily_protein":135},'
        '"exercise":{"total_workouts":14,"active_days":12,'
        '"total_calories_burned":4200},"mood":{"avg_mood":7.8},'
        '"sleep":{"avg_duration_hours":7.4,"avg_sleep_score":88},'
        '"biometrics":{"weight_entries":9,"weights":[]}}'
    ) == {
        "food_days_logged_30d": 28,
        "avg_daily_calories_30d": 1950,
        "avg_daily_protein_30d": 135,
        "workouts_30d": 14,
        "active_days_30d": 12,
        "exercise_calories_30d": 4200,
        "avg_mood_30d": 7.8,
        "avg_sleep_duration_30d": 7.4,
        "avg_sleep_score_30d": 88,
        "weight_entries_30d": 9,
    }


def test_parse_habits_and_today_completion() -> None:
    """Habit names, UUIDs, and explicit daily values remain deterministic."""

    habit_id = "11111111-1111-1111-1111-111111111111"
    assert parse_habit_list(
        f"# Available Habits\n\n**Morning walk**\n  ID: {habit_id}"
    ) == {
        habit_id: {
            "id": habit_id,
            "name": "Morning walk",
            "completed": None,
        }
    }
    assert (
        parse_habit_completion(
            "# Habit History\n\n2026-08-26: ✅ Completed", "2026-08-26"
        )
        is True
    )
    assert (
        parse_habit_completion("# Habit History\n\n2026-08-26: ❌ Missed", "2026-08-26")
        is False
    )
    assert (
        parse_habit_completion("# Habit History\n\nNo results found.", "2026-08-26")
        is None
    )
