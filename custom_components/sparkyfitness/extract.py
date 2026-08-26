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


def parse_exercise_search(text: str) -> list[dict[str, str]]:
    """Extract names and UUIDs from the stable exercise-search result."""

    matches = re.finditer(
        r"^\*\*(?P<name>.+?)\*\*.*?^\s*ID:\s*(?P<id>[0-9a-fA-F-]{36})\s*$",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return [{"name": match.group("name"), "id": match.group("id")} for match in matches]
