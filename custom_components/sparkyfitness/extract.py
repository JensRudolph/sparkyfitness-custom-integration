"""Parse the stable output shapes exposed by current SparkyFitness MCP tools."""

from __future__ import annotations

import json
import re
from typing import Any

from .exceptions import SparkyFitnessMcpError

_WEIGHT_RE = re.compile(r"^- \*\*Weight:\*\*\s+([0-9.]+)\s+([^\s]+)$", re.MULTILINE)
_STEPS_RE = re.compile(r"^- \*\*Steps:\*\*\s+(\d+)$", re.MULTILINE)
_BODY_FAT_RE = re.compile(r"^- \*\*Body Fat:\*\*\s+([0-9.]+)%$", re.MULTILINE)
_MOOD_RE = re.compile(
    r"^## Mood\s*$.*?^-\s+([0-9]+(?:\.[0-9]+)?)/10", re.MULTILINE | re.DOTALL
)
_SLEEP_RE = re.compile(
    r"^## Sleep\s*$.*?^-\s+(?:(\d+)h\s*)?(?:(\d+)m)?(?:\s*\|\s*score:\s*([0-9.]+)/100)?",
    re.MULTILINE | re.DOTALL,
)


def extract_json(text: str) -> Any:
    """Extract a JSON object or array from an MCP text content block."""

    stripped = text.strip()
    candidates = [
        index for index in (stripped.find("{"), stripped.find("[")) if index >= 0
    ]
    if not candidates:
        raise SparkyFitnessMcpError("The MCP tool response did not contain JSON")
    try:
        return json.loads(stripped[min(candidates) :])
    except json.JSONDecodeError as err:
        raise SparkyFitnessMcpError("The MCP tool returned malformed JSON") from err


def parse_health_summary(text: str) -> dict[str, Any]:
    """Project the documented health-summary JSON onto entity keys."""

    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise SparkyFitnessMcpError("Health summary was not a JSON object")

    nutrition = payload.get("nutrition") or {}
    fitness = payload.get("fitness") or {}
    vitals = payload.get("vitals") or {}
    hydration = payload.get("hydration") or {}
    latest_weight = vitals.get("latest_weight")

    result: dict[str, Any] = {
        "calories_today": nutrition.get("total_calories"),
        "protein_today": nutrition.get("avg_protein"),
        "carbs_today": nutrition.get("avg_carbs"),
        "fat_today": nutrition.get("avg_fat"),
        "water_today": hydration.get("total_water_ml"),
        "exercise_count_today": fitness.get("workout_count"),
    }
    if isinstance(latest_weight, dict):
        result["weight"] = latest_weight.get("weight")
        result["weight_unit"] = "kg"
    return result


def parse_checkin_diary(text: str) -> dict[str, Any]:
    """Parse the server's documented check-in Markdown projection."""

    result: dict[str, Any] = {}
    if match := _WEIGHT_RE.search(text):
        result["weight"] = float(match.group(1))
        result["weight_unit"] = match.group(2)
    if match := _STEPS_RE.search(text):
        result["steps_today"] = int(match.group(1))
    if match := _BODY_FAT_RE.search(text):
        result["body_fat"] = float(match.group(1))
    if match := _MOOD_RE.search(text):
        result["mood"] = float(match.group(1))
    if match := _SLEEP_RE.search(text):
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        if hours or minutes:
            result["sleep_duration"] = round(hours + minutes / 60, 2)
        if match.group(3) is not None:
            result["sleep_score"] = float(match.group(3))
    return result


def parse_fasting_status(text: str) -> dict[str, Any] | None:
    """Parse a fasting status response."""

    if "No active fasting session" in text:
        return None
    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise SparkyFitnessMcpError("Fasting status was not a JSON object")
    return {
        "start_time": payload.get("start_time"),
        "end_time": payload.get("end_time"),
        "fasting_status": payload.get("fasting_status"),
        "fasting_type": payload.get("fasting_type"),
    }


def parse_logging_streak(text: str) -> int | None:
    """Parse the current logging streak."""

    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise SparkyFitnessMcpError("Logging streak was not a JSON object")
    value = payload.get("current_streak")
    return int(value) if value is not None else None


def parse_goal_snapshot(text: str) -> dict[str, Any]:
    """Project the structured current goal snapshot onto entity keys."""

    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise SparkyFitnessMcpError("Goal snapshot was not a JSON object")
    return {
        entity_key: payload.get(mcp_key)
        for entity_key, mcp_key in {
            "calorie_goal": "calories",
            "protein_goal": "protein",
            "carbs_goal": "carbs",
            "fat_goal": "fat",
            "water_goal": "water_goal_ml",
        }.items()
    }


def parse_30_day_trends(text: str) -> dict[str, Any]:
    """Project stable structured 30-day aggregates onto entity keys."""

    payload = extract_json(text)
    if not isinstance(payload, dict):
        raise SparkyFitnessMcpError("30-day trends were not a JSON object")

    sections: dict[str, dict[str, Any]] = {}
    for section in ("food", "exercise", "mood", "sleep", "biometrics"):
        value = payload.get(section)
        sections[section] = value if isinstance(value, dict) else {}

    food = sections["food"]
    exercise = sections["exercise"]
    mood = sections["mood"]
    sleep = sections["sleep"]
    biometrics = sections["biometrics"]
    return {
        "food_days_logged_30d": food.get("days_logged"),
        "avg_daily_calories_30d": food.get("avg_daily_calories"),
        "avg_daily_protein_30d": food.get("avg_daily_protein"),
        "workouts_30d": exercise.get("total_workouts"),
        "active_days_30d": exercise.get("active_days"),
        "exercise_calories_30d": exercise.get("total_calories_burned"),
        "avg_mood_30d": mood.get("avg_mood"),
        "avg_sleep_duration_30d": sleep.get("avg_duration_hours"),
        "avg_sleep_score_30d": sleep.get("avg_sleep_score"),
        "weight_entries_30d": biometrics.get("weight_entries"),
    }


def parse_exercise_search(text: str) -> list[dict[str, str]]:
    """Extract names and UUIDs from the stable exercise-search result."""

    matches = re.finditer(
        r"^\*\*(?P<name>.+?)\*\*.*?^\s*ID:\s*(?P<id>[0-9a-fA-F-]{36})\s*$",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return [{"name": match.group("name"), "id": match.group("id")} for match in matches]


def parse_habit_list(text: str) -> dict[str, dict[str, Any]]:
    """Extract stable habit IDs and display names from the MCP list."""

    if not text.lstrip().startswith("# Available Habits"):
        raise SparkyFitnessMcpError("Habit list response had an unexpected format")
    matches = re.finditer(
        r"^\*\*(?P<name>.+?)\*\*\s*$\s*^\s*ID:\s*"
        r"(?P<id>[0-9a-fA-F-]{36})\s*$",
        text,
        re.MULTILINE,
    )
    return {
        match.group("id"): {
            "id": match.group("id"),
            "name": match.group("name"),
            "completed": None,
        }
        for match in matches
    }


def parse_habit_completion(text: str, entry_date: str) -> bool | None:
    """Return an explicitly completed/missed habit value for one date."""

    if not text.lstrip().startswith("# Habit History"):
        raise SparkyFitnessMcpError("Habit history response had an unexpected format")
    match = re.search(
        rf"^{re.escape(entry_date)}:\s*(?:✅\s*)?(Completed)|"
        rf"^{re.escape(entry_date)}:\s*(?:❌\s*)?(Missed)",
        text,
        re.MULTILINE,
    )
    if match is None:
        return None
    return match.group(1) is not None
