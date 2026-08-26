"""Tests for the direct Streamable HTTP MCP client."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import aiohttp
import pytest

from custom_components.sparkyfitness.api import (
    SparkyFitnessMcpClient,
    normalize_mcp_endpoint,
)
from custom_components.sparkyfitness.const import (
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_EXERCISE,
    TOOL_EXERCISE_DIARY,
    TOOL_FOOD,
    TOOL_FOOD_DIARY,
    TOOL_GOAL_SNAPSHOT,
    TOOL_GOALS,
    TOOL_HABITS,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
    TOOL_SEARCH_EXERCISES,
    TOOL_SEARCH_FOODS,
    TOOL_STREAK,
)
from custom_components.sparkyfitness.exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessTimeoutError,
    SparkyFitnessToolError,
    SparkyFitnessUnsupportedFeatureError,
)
from custom_components.sparkyfitness.models import McpTool

ENTRY_ID = "11111111-1111-1111-1111-111111111111"


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(
        self,
        body: dict[str, Any] | str,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        enter_delay: float = 0,
    ) -> None:
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self._text = body if isinstance(body, str) else json.dumps(body)
        self._enter_delay = enter_delay

    async def __aenter__(self):
        if self._enter_delay:
            await asyncio.sleep(self._enter_delay)
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self) -> str:
        return self._text

    async def read(self) -> bytes:
        return self._text.encode()


class FakeSession:
    """Route posted JSON-RPC messages to a response factory."""

    def __init__(self, route: Callable[[dict[str, Any]], FakeResponse]) -> None:
        self.route = route
        self.requests: list[dict[str, Any]] = []

    def post(self, _url: str, *, json: dict[str, Any], **_kwargs) -> FakeResponse:
        self.requests.append(json)
        return self.route(json)

    def delete(self, *_args, **_kwargs) -> FakeResponse:
        return FakeResponse({}, status=204)


def _success_route(message: dict[str, Any]) -> FakeResponse:
    request_id = message["id"]
    if message["method"] == "initialize":
        result = {
            "protocolVersion": "2025-11-25",
            "serverInfo": {"name": "sparkyfitness-mcp-server", "version": "1.6.3"},
        }
    elif message["method"] == "tools/list":
        result = {
            "tools": [
                {
                    "name": "sparky_manage_checkin",
                    "description": "check-in",
                    "inputSchema": {"type": "object"},
                }
            ]
        }
    else:
        result = {"content": [{"type": "text", "text": "ok"}]}
    return FakeResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def test_normalize_mcp_endpoint() -> None:
    """Base URLs and endpoint URLs normalize deterministically."""

    assert normalize_mcp_endpoint("https://example.com/") == "https://example.com/mcp"
    assert (
        normalize_mcp_endpoint("https://example.com/mcp/") == "https://example.com/mcp"
    )
    assert (
        normalize_mcp_endpoint("https://example.com/base")
        == "https://example.com/base/mcp"
    )
    with pytest.raises(ValueError):
        normalize_mcp_endpoint("example.com")


async def test_initialize_list_tools_and_call() -> None:
    """The client initializes, discovers schemas, and dispatches a tool call."""

    session = FakeSession(_success_route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    tools = await client.async_test_connection()
    assert list(tools) == ["sparky_manage_checkin"]
    assert client.server_version == "1.6.3"
    assert (
        await client.async_call_tool(
            "sparky_manage_checkin", {"action": "get_fasting_status"}
        )
        == "ok"
    )
    assert [request["method"] for request in session.requests] == [
        "initialize",
        "tools/list",
        "tools/call",
    ]


async def test_tool_error_is_raised() -> None:
    """MCP isError results do not masquerade as successful writes."""

    def route(message):
        if message["method"] != "tools/call":
            return _success_route(message)
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "Error [VALIDATION]"}],
                },
            }
        )

    client = SparkyFitnessMcpClient(FakeSession(route), "https://example.com", "secret")
    await client.async_test_connection()
    with pytest.raises(SparkyFitnessToolError, match="VALIDATION"):
        await client.async_call_tool("sparky_manage_checkin", {})


async def test_advertised_action_schema_is_enforced() -> None:
    """Writes absent from a server's advertised schema fail before dispatch."""

    def route(message):
        if message["method"] != "tools/list":
            return _success_route(message)
        return FakeResponse(
            {
                "jsonrpc": "2.0",
                "id": message["id"],
                "result": {
                    "tools": [
                        {
                            "name": "sparky_manage_checkin",
                            "description": "check-in",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "action": {"enum": ["get_fasting_status"]}
                                },
                            },
                        }
                    ]
                },
            }
        )

    session = FakeSession(route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    await client.async_test_connection()

    with pytest.raises(
        SparkyFitnessUnsupportedFeatureError, match="does not support action"
    ):
        await client.async_call_tool(
            "sparky_manage_checkin", {"action": "log_biometrics"}
        )

    assert [request["method"] for request in session.requests] == [
        "initialize",
        "tools/list",
        "tools/list",
    ]


async def test_sse_notification_is_skipped_before_matching_response() -> None:
    """An ID-less progress notification cannot replace the requested result."""

    body = (
        'data: {"jsonrpc":"2.0","method":"notifications/progress",'
        '"params":{"progress":1}}\n\n'
        'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'
    )
    response = FakeResponse(
        body,
        headers={"Content-Type": "text/event-stream"},
    )
    client = SparkyFitnessMcpClient(
        FakeSession(lambda _: response), "https://example.com", "secret"
    )
    assert await client._request("tools/list") == {"tools": []}


@pytest.mark.parametrize("status", [401, 403])
async def test_invalid_auth(status: int) -> None:
    """Both common authorization status codes map to reauthentication."""

    client = SparkyFitnessMcpClient(
        FakeSession(lambda _: FakeResponse({}, status=status)),
        "https://example.com",
        "secret",
    )
    with pytest.raises(SparkyFitnessAuthenticationError):
        await client.async_connect()


async def test_timeout_and_connection_drop() -> None:
    """Timeout and connection drop have distinct stable exception classes."""

    slow = SparkyFitnessMcpClient(
        FakeSession(lambda _: FakeResponse({}, enter_delay=0.05)),
        "https://example.com",
        "secret",
        timeout=0.001,
    )
    with pytest.raises(SparkyFitnessTimeoutError):
        await slow.async_connect()

    class BrokenSession(FakeSession):
        def post(self, *_args, **_kwargs):
            raise aiohttp.ClientConnectionError

    broken = SparkyFitnessMcpClient(
        BrokenSession(_success_route), "https://example.com", "secret"
    )
    with pytest.raises(SparkyFitnessConnectionError):
        await broken.async_connect()


async def test_reconnect_after_disconnect() -> None:
    """A disconnected client initializes again before its next request."""

    session = FakeSession(_success_route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    await client.async_test_connection()
    await client.async_disconnect()
    await client.async_list_tools()
    assert [request["method"] for request in session.requests].count("initialize") == 2


async def test_extended_write_wrappers_use_current_mcp_actions() -> None:
    """Update/delete/fasting wrappers preserve reviewed tool and action names."""

    session = FakeSession(_success_route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    client._connected = True
    client.tools = {
        name: McpTool(name=name, description="", input_schema={})
        for name in (TOOL_CHECKIN, TOOL_FOOD, TOOL_EXERCISE)
    }

    await client.async_update_food_entry(ENTRY_ID, quantity=1.5)
    await client.async_delete_food_entry(ENTRY_ID, "food_entry")
    await client.async_update_exercise_entry(ENTRY_ID, notes="Corrected")
    await client.async_delete_exercise_entry(ENTRY_ID)
    await client.async_log_fasting(
        "2026-08-26T18:00:00+00:00",
        end_time="2026-08-27T10:00:00+00:00",
        fasting_status="COMPLETED",
        fasting_type="16:8",
    )

    calls = [request["params"] for request in session.requests]
    assert [call["name"] for call in calls] == [
        TOOL_FOOD,
        TOOL_FOOD,
        TOOL_EXERCISE,
        TOOL_EXERCISE,
        TOOL_CHECKIN,
    ]
    assert [call["arguments"]["action"] for call in calls] == [
        "update_entry",
        "delete_entry",
        "update_exercise_entry",
        "delete_exercise_entry",
        "log_fasting",
    ]


async def test_read_wrappers_use_only_advertised_mcp_tools_and_actions() -> None:
    """Read helpers map to the current dedicated and managed MCP surface."""

    session = FakeSession(_success_route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    client._connected = True
    client.tools = {
        name: McpTool(name=name, description="", input_schema={})
        for name in (
            TOOL_FOOD_DIARY,
            TOOL_SEARCH_FOODS,
            TOOL_EXERCISE_DIARY,
            TOOL_SEARCH_EXERCISES,
            TOOL_EXERCISE,
            TOOL_HABITS,
        )
    }

    await client.async_list_food_diary(date="2026-08-26")
    await client.async_search_food("Oats", limit=10, offset=5)
    await client.async_list_exercise_diary(
        start_date="2026-08-25", end_date="2026-08-26"
    )
    await client.async_search_exercise(
        "Press", muscle_group="Chest", equipment="Barbell"
    )
    await client.async_list_workout_presets()
    await client.async_list_habits()
    await client.async_get_habit_history(
        ENTRY_ID, start_date="2026-08-01", end_date="2026-08-26"
    )

    calls = [request["params"] for request in session.requests]
    assert [call["name"] for call in calls] == [
        TOOL_FOOD_DIARY,
        TOOL_SEARCH_FOODS,
        TOOL_EXERCISE_DIARY,
        TOOL_SEARCH_EXERCISES,
        TOOL_EXERCISE,
        TOOL_HABITS,
        TOOL_HABITS,
    ]
    assert calls[4]["arguments"] == {"action": "get_workout_presets"}
    assert calls[5]["arguments"] == {"action": "list_habits"}
    assert calls[6]["arguments"]["action"] == "get_habit_history"


async def test_priority_and_write_wrappers_preserve_reviewed_arguments() -> None:
    """Priority reads and common writes cannot drift from reviewed mappings."""

    session = FakeSession(_success_route)
    client = SparkyFitnessMcpClient(session, "https://example.com", "secret")
    client._connected = True
    client.tools = {
        name: McpTool(name=name, description="", input_schema={})
        for name in (
            TOOL_30_DAY_TRENDS,
            TOOL_CHECKIN,
            TOOL_EXERCISE,
            TOOL_FOOD,
            TOOL_GOAL_SNAPSHOT,
            TOOL_GOALS,
            TOOL_HABITS,
            TOOL_HEALTH_SUMMARY,
            TOOL_NUTRITION_SUMMARY,
            TOOL_STREAK,
        )
    }

    assert await client.async_get_today_summary() == "ok"
    assert await client.async_get_nutrition_summary() == "ok"
    assert await client.async_get_checkin() == "ok"
    assert await client.async_get_fasting_status() == "ok"
    assert await client.async_get_logging_streak() == "ok"
    assert await client.async_get_goal_snapshot() == "ok"
    assert await client.async_get_30_day_trends() == "ok"
    await client.async_log_weight(84.7, "kg", "today")
    await client.async_log_water(750, "today")
    await client.async_log_mood(8, "today", notes="Good", mood_tags=["calm"])
    await client.async_log_sleep(
        "today",
        duration_seconds=28800,
        bedtime="22:00",
        wake_time="06:00",
        source="watch",
    )
    await client.async_log_custom_metric(
        "Grip", 45.5, "today", unit="kg", notes="Left hand"
    )
    await client.async_log_food(food="Oats", quantity=1)
    await client.async_log_exercise(exercise="Walk", duration_minutes=30)
    await client.async_create_exercise(name="Carry", category="Strength")
    await client.async_log_workout_preset(preset_name="Morning")
    await client.async_set_goals(start_date="today", calorie_goal=2000)
    await client.async_log_habit(ENTRY_ID, "today", True)

    calls = [request["params"] for request in session.requests]
    assert [call["name"] for call in calls[:7]] == [
        TOOL_HEALTH_SUMMARY,
        TOOL_NUTRITION_SUMMARY,
        TOOL_CHECKIN,
        TOOL_CHECKIN,
        TOOL_STREAK,
        TOOL_GOAL_SNAPSHOT,
        TOOL_30_DAY_TRENDS,
    ]
    assert calls[9]["arguments"] == {
        "action": "log_mood",
        "mood_value": 8,
        "entry_date": "today",
        "notes": "Good",
        "mood_tags": ["calm"],
    }
    assert calls[10]["arguments"]["duration_seconds"] == 28800
    assert calls[11]["arguments"]["category_name"] == "Grip"
    assert calls[-1]["arguments"] == {
        "action": "log_habit",
        "habit_id": ENTRY_ID,
        "entry_date": "today",
        "completed": True,
    }
