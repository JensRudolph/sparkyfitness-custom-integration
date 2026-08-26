"""Local projections of the existing SparkyFitness fasting status."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_PROTOCOL_RE = re.compile(r"^\s*(?P<fast>\d+(?:\.\d+)?)\s*:\s*\d+(?:\.\d+)?\s*$")


def fasting_metrics(
    fasting: dict[str, Any] | None, *, now: datetime | None = None
) -> dict[str, Any]:
    """Calculate display metrics without inventing missing server data."""

    if not fasting or fasting.get("fasting_status", "ACTIVE") != "ACTIVE":
        return {}
    start = dt_util.parse_datetime(str(fasting.get("start_time") or ""))
    if start is None or start.tzinfo is None:
        return {}
    current = now or datetime.now(UTC)
    elapsed = max(
        0.0, (dt_util.as_utc(current) - dt_util.as_utc(start)).total_seconds()
    )
    result: dict[str, Any] = {
        "elapsed_seconds": round(elapsed),
    }

    match = _PROTOCOL_RE.fullmatch(str(fasting.get("fasting_type") or ""))
    if match is None:
        return result
    target_seconds = float(match.group("fast")) * 3600
    if target_seconds <= 0:
        return result
    result.update(
        {
            "target_end": dt_util.as_utc(start) + timedelta(seconds=target_seconds),
            "remaining_seconds": round(max(0.0, target_seconds - elapsed)),
            "progress": round(elapsed / target_seconds * 100, 1),
            "goal_reached": elapsed >= target_seconds,
        }
    )
    return result
