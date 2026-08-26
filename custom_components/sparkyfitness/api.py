"""Direct asynchronous MCP client for SparkyFitness."""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from .const import (
    EXPECTED_TOOLS,
    INTEGRATION_VERSION,
    MCP_PROTOCOL_VERSION,
    NAME,
    REQUEST_TIMEOUT_SECONDS,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_EXERCISE,
    TOOL_FOOD,
    TOOL_GOAL_SNAPSHOT,
    TOOL_GOALS,
    TOOL_HABITS,
    TOOL_HEALTH_SUMMARY,
    TOOL_STREAK,
)
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessMcpError,
    SparkyFitnessSslError,
    SparkyFitnessTimeoutError,
    SparkyFitnessToolError,
    SparkyFitnessUnsupportedFeatureError,
)
from .extract import parse_exercise_search
from .models import McpTool

_LOGGER = logging.getLogger(__name__)


def normalize_mcp_endpoint(url: str) -> str:
    """Normalize a SparkyFitness base URL or MCP URL."""

    value = url.strip()
    if not value:
        raise ValueError("URL is required")
    split = urlsplit(value)
    if split.scheme not in {"http", "https"} or not split.hostname:
        raise ValueError("URL must use http or https and include a hostname")
    if split.username or split.password:
        raise ValueError("Credentials must not be embedded in the URL")

    path = split.path.rstrip("/")
    if not path.lower().endswith("/mcp"):
        path = f"{path}/mcp" if path else "/mcp"
    return urlunsplit((split.scheme.lower(), split.netloc, path, "", ""))


class SparkyFitnessMcpClient:
    """Small MCP client using Home Assistant's shared aiohttp session.

    SparkyFitness serves a stateless Streamable HTTP endpoint with JSON responses.
    SSE responses are accepted as well for compatibility with other server releases.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        api_key: str,
        *,
        verify_ssl: bool = True,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the client without opening a connection."""

        self._session = session
        self.endpoint = normalize_mcp_endpoint(endpoint)
        self._api_key = api_key
        self._verify_ssl = verify_ssl
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._request_id = 0
        self._session_id: str | None = None
        self._protocol_version = MCP_PROTOCOL_VERSION
        self._connected = False
        self.tools: dict[str, McpTool] = {}
        self.server_info: dict[str, Any] = {}

    @property
    def connected(self) -> bool:
        """Return whether MCP initialization has completed."""

        return self._connected

    @property
    def server_version(self) -> str | None:
        """Return the version advertised in the MCP initialize response."""

        version = self.server_info.get("version")
        return str(version) if version is not None else None

    async def async_connect(self) -> None:
        """Initialize MCP and retain session metadata when supplied."""

        if self._connected:
            return
        result = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": NAME, "version": INTEGRATION_VERSION},
            },
            include_protocol_header=False,
        )
        protocol_version = result.get("protocolVersion")
        if isinstance(protocol_version, str):
            self._protocol_version = protocol_version
        server_info = result.get("serverInfo")
        if isinstance(server_info, dict):
            self.server_info = server_info
        self._connected = True

    async def async_disconnect(self) -> None:
        """Release protocol state without closing Home Assistant's session."""

        if self._session_id:
            headers = self._headers(include_protocol=True)
            try:
                async with asyncio.timeout(
                    self._timeout.total or REQUEST_TIMEOUT_SECONDS
                ):
                    async with self._session.delete(
                        self.endpoint,
                        headers=headers,
                        ssl=self._verify_ssl,
                    ):
                        pass
            except TimeoutError, aiohttp.ClientError:
                _LOGGER.debug("MCP session cleanup failed")
        self._session_id = None
        self._connected = False

    async def async_list_tools(self) -> dict[str, McpTool]:
        """Discover and cache available MCP tools."""

        if not self._connected:
            await self.async_connect()
        result = await self._request("tools/list")
        raw_tools = result.get("tools")
        if not isinstance(raw_tools, list):
            raise SparkyFitnessMcpError("MCP tools/list did not return a tool list")

        discovered: dict[str, McpTool] = {}
        for raw_tool in raw_tools:
            if not isinstance(raw_tool, dict) or not isinstance(
                raw_tool.get("name"), str
            ):
                continue
            schema = raw_tool.get("inputSchema")
            discovered[raw_tool["name"]] = McpTool(
                name=raw_tool["name"],
                description=str(raw_tool.get("description") or ""),
                input_schema=schema if isinstance(schema, dict) else {},
            )
        self.tools = discovered
        return discovered

    async def async_test_connection(self) -> dict[str, McpTool]:
        """Initialize, discover tools, and verify this is SparkyFitness."""

        await self.async_connect()
        tools = await self.async_list_tools()
        if not EXPECTED_TOOLS.intersection(tools):
            raise SparkyFitnessMcpError(
                "The MCP server does not expose characteristic SparkyFitness tools"
            )
        return tools

    async def async_call_tool(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> Any:
        """Call one discovered MCP tool and return its content."""

        if not self._connected:
            await self.async_connect()
        if not self.tools:
            await self.async_list_tools()
        if name not in self.tools:
            raise SparkyFitnessUnsupportedFeatureError(
                f'The connected SparkyFitness server does not expose "{name}"'
            )
        call_arguments = dict(arguments or {})
        action = call_arguments.get("action")
        action_schema = (
            self.tools[name].input_schema.get("properties", {}).get("action", {})
        )
        advertised_actions = action_schema.get("enum")
        if (
            isinstance(action, str)
            and isinstance(advertised_actions, list)
            and action not in advertised_actions
        ):
            raise SparkyFitnessUnsupportedFeatureError(
                f'The connected SparkyFitness schema does not support action "{action}" '
                f'on tool "{name}"'
            )

        result = await self._request(
            "tools/call", {"name": name, "arguments": call_arguments}
        )
        if result.get("isError") is True:
            message = (
                self._content_text(result.get("content")) or f'Tool "{name}" failed'
            )
            raise SparkyFitnessToolError(message)
        if "structuredContent" in result:
            return result["structuredContent"]
        return self._content_text(result.get("content"))

    async def async_get_today_summary(self) -> str:
        """Return today's structured health summary."""

        return str(await self.async_call_tool(TOOL_HEALTH_SUMMARY))

    async def async_get_checkin(self) -> str:
        """Return today's check-in diary."""

        return str(
            await self.async_call_tool(TOOL_CHECKIN, {"action": "list_checkin_diary"})
        )

    async def async_get_fasting_status(self) -> str:
        """Return the current fasting status."""

        return str(
            await self.async_call_tool(TOOL_CHECKIN, {"action": "get_fasting_status"})
        )

    async def async_get_logging_streak(self) -> str:
        """Return the current logging streak."""

        return str(await self.async_call_tool(TOOL_STREAK))

    async def async_get_goal_snapshot(self) -> str:
        """Return the goals active today."""

        return str(await self.async_call_tool(TOOL_GOAL_SNAPSHOT))

    async def async_get_30_day_trends(self) -> str:
        """Return the current structured 30-day aggregates."""

        return str(await self.async_call_tool(TOOL_30_DAY_TRENDS))

    async def async_log_weight(self, weight: float, unit: str, entry_date: str) -> Any:
        """Log weight through the check-in MCP tool."""

        return await self.async_log_biometrics(
            entry_date=entry_date, weight=weight, weight_unit=unit
        )

    async def async_log_biometrics(self, **values: Any) -> Any:
        """Log biometrics through the check-in MCP tool."""

        return await self.async_call_tool(
            TOOL_CHECKIN, {"action": "log_biometrics", **values}
        )

    async def async_log_water(self, amount_ml: float, entry_date: str) -> Any:
        """Log water through the food MCP tool."""

        return await self.async_call_tool(
            TOOL_FOOD,
            {"action": "log_water", "amount_ml": amount_ml, "entry_date": entry_date},
        )

    async def async_log_mood(
        self,
        mood: int,
        entry_date: str,
        *,
        notes: str | None = None,
        mood_tags: Sequence[str] | None = None,
    ) -> Any:
        """Log mood through the check-in MCP tool."""

        arguments: dict[str, Any] = {
            "action": "log_mood",
            "mood_value": mood,
            "entry_date": entry_date,
        }
        if notes:
            arguments["notes"] = notes
        if mood_tags:
            arguments["mood_tags"] = list(mood_tags)
        return await self.async_call_tool(TOOL_CHECKIN, arguments)

    async def async_log_sleep(
        self,
        entry_date: str,
        *,
        duration_seconds: int | None = None,
        bedtime: str | None = None,
        wake_time: str | None = None,
        source: str | None = None,
    ) -> Any:
        """Log sleep through the check-in MCP tool."""

        arguments: dict[str, Any] = {"action": "log_sleep", "entry_date": entry_date}
        for key, value in {
            "duration_seconds": duration_seconds,
            "bedtime": bedtime,
            "wake_time": wake_time,
            "source": source,
        }.items():
            if value is not None:
                arguments[key] = value
        return await self.async_call_tool(TOOL_CHECKIN, arguments)

    async def async_log_custom_metric(
        self,
        name: str,
        value: str | float,
        entry_date: str,
        *,
        unit: str | None = None,
        notes: str | None = None,
    ) -> Any:
        """Log a value to an existing custom metric category."""

        arguments: dict[str, Any] = {
            "action": "log_custom_metric",
            "category_name": name,
            "value": value,
            "entry_date": entry_date,
        }
        if unit:
            arguments["unit"] = unit
        if notes:
            arguments["notes"] = notes
        return await self.async_call_tool(TOOL_CHECKIN, arguments)

    async def async_log_food(self, **values: Any) -> Any:
        """Log an existing internal SparkyFitness food."""

        return await self.async_call_tool(TOOL_FOOD, {"action": "log_food", **values})

    async def async_update_food_entry(self, entry_id: str, **values: Any) -> Any:
        """Update one food diary entry by its stable MCP identifier."""

        return await self.async_call_tool(
            TOOL_FOOD, {"action": "update_entry", "entry_id": entry_id, **values}
        )

    async def async_delete_food_entry(self, entry_id: str, entry_type: str) -> Any:
        """Delete one food diary entry by its stable MCP identifier."""

        return await self.async_call_tool(
            TOOL_FOOD,
            {
                "action": "delete_entry",
                "entry_id": entry_id,
                "entry_type": entry_type,
            },
        )

    async def async_log_exercise(self, **values: Any) -> Any:
        """Log exercise data, including structured set data."""

        return await self.async_call_tool(
            TOOL_EXERCISE, {"action": "log_exercise", **values}
        )

    async def async_create_exercise(self, **values: Any) -> Any:
        """Create an exercise; SparkyFitness de-duplicates exact names."""

        return await self.async_call_tool(
            TOOL_EXERCISE, {"action": "create_exercise", **values}
        )

    async def async_update_exercise_entry(self, entry_id: str, **values: Any) -> Any:
        """Update one exercise diary entry by its stable MCP identifier."""

        return await self.async_call_tool(
            TOOL_EXERCISE,
            {"action": "update_exercise_entry", "entry_id": entry_id, **values},
        )

    async def async_delete_exercise_entry(self, entry_id: str) -> Any:
        """Delete one exercise diary entry by its stable MCP identifier."""

        return await self.async_call_tool(
            TOOL_EXERCISE,
            {"action": "delete_exercise_entry", "entry_id": entry_id},
        )

    async def async_create_workout_preset(
        self, name: str, exercise_names: Sequence[str]
    ) -> Any:
        """Resolve unambiguous exact exercise names and create a preset."""

        exercise_ids: list[str] = []
        for exercise_name in exercise_names:
            result = await self.async_call_tool(
                TOOL_EXERCISE,
                {
                    "action": "search_exercises",
                    "searchTerm": exercise_name,
                    "limit": 20,
                    "offset": 0,
                },
            )
            candidates = [
                item
                for item in parse_exercise_search(str(result))
                if item["name"].casefold() == exercise_name.casefold()
            ]
            if len(candidates) != 1:
                qualifier = "not found" if not candidates else "ambiguous"
                raise SparkyFitnessToolError(
                    f'Exercise "{exercise_name}" is {qualifier}; preset was not created'
                )
            exercise_ids.append(candidates[0]["id"])
        return await self.async_call_tool(
            TOOL_EXERCISE,
            {
                "action": "create_workout_preset",
                "name": name,
                "exercise_ids": exercise_ids,
            },
        )

    async def async_log_workout_preset(self, **values: Any) -> Any:
        """Log a workout preset."""

        return await self.async_call_tool(
            TOOL_EXERCISE, {"action": "log_workout_preset", **values}
        )

    async def async_set_goals(self, **values: Any) -> Any:
        """Set goals from an effective date."""

        return await self.async_call_tool(TOOL_GOALS, {"action": "set_goals", **values})

    async def async_log_fasting(
        self,
        start_time: str,
        *,
        end_time: str | None = None,
        fasting_status: str = "ACTIVE",
        fasting_type: str | None = None,
    ) -> Any:
        """Log a new active fast or a complete fasting window."""

        arguments: dict[str, Any] = {
            "action": "log_fasting",
            "start_time": start_time,
            "fasting_status": fasting_status,
        }
        if end_time is not None:
            arguments["end_time"] = end_time
        if fasting_type is not None:
            arguments["fasting_type"] = fasting_type
        return await self.async_call_tool(TOOL_CHECKIN, arguments)

    async def async_log_habit(
        self, habit_id: str, entry_date: str, completed: bool
    ) -> Any:
        """Log a habit completion."""

        return await self.async_call_tool(
            TOOL_HABITS,
            {
                "action": "log_habit",
                "habit_id": habit_id,
                "entry_date": entry_date,
                "completed": completed,
            },
        )

    async def _request(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        *,
        include_protocol_header: bool = True,
    ) -> dict[str, Any]:
        """Perform one JSON-RPC request over Streamable HTTP."""

        self._request_id += 1
        request_id = self._request_id
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers = self._headers(include_protocol=include_protocol_header)
        try:
            async with asyncio.timeout(self._timeout.total or REQUEST_TIMEOUT_SECONDS):
                async with self._session.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                    ssl=self._verify_ssl,
                ) as response:
                    if response.status in {401, 403}:
                        await response.read()
                        raise SparkyFitnessAuthenticationError(
                            "SparkyFitness rejected the API key"
                        )
                    if response.status >= 400:
                        await response.read()
                        raise SparkyFitnessConnectionError(
                            f"MCP endpoint returned HTTP {response.status}"
                        )
                    if session_id := response.headers.get("Mcp-Session-Id"):
                        self._session_id = session_id
                    message = await self._decode_response(response, request_id)
        except SparkyFitnessAuthenticationError:
            raise
        except SparkyFitnessConnectionError:
            raise
        except TimeoutError as err:
            raise SparkyFitnessTimeoutError("MCP request timed out") from err
        except (
            aiohttp.ClientConnectorCertificateError,
            aiohttp.ClientSSLError,
            ssl.SSLError,
        ) as err:
            raise SparkyFitnessSslError("TLS certificate verification failed") from err
        except aiohttp.ClientError as err:
            raise SparkyFitnessConnectionError(
                "Could not connect to MCP endpoint"
            ) from err

        if message.get("id") not in {request_id, None}:
            raise SparkyFitnessMcpError("MCP returned a mismatched response id")
        if error := message.get("error"):
            if isinstance(error, dict):
                code = error.get("code")
                detail = error.get("message") or "Unknown MCP error"
                raise SparkyFitnessMcpError(f"MCP error {code}: {detail}")
            raise SparkyFitnessMcpError("MCP returned an invalid error response")
        result = message.get("result")
        if not isinstance(result, dict):
            raise SparkyFitnessMcpError("MCP response did not contain an object result")
        return result

    async def _decode_response(
        self, response: aiohttp.ClientResponse, request_id: int
    ) -> dict[str, Any]:
        """Decode JSON or Streamable HTTP SSE response data."""

        text = await response.text()
        content_type = response.headers.get("Content-Type", "").lower()
        try:
            if "text/event-stream" not in content_type:
                decoded = json.loads(text)
                if isinstance(decoded, dict):
                    return decoded
            for line in text.splitlines():
                if not line.startswith("data:"):
                    continue
                candidate = json.loads(line[5:].strip())
                if isinstance(candidate, dict) and candidate.get("id") in {
                    request_id,
                    None,
                }:
                    return candidate
        except json.JSONDecodeError as err:
            raise SparkyFitnessMcpError("MCP endpoint returned invalid JSON") from err
        raise SparkyFitnessMcpError("MCP endpoint returned no JSON-RPC response")

    def _headers(self, *, include_protocol: bool) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if include_protocol:
            headers["MCP-Protocol-Version"] = self._protocol_version
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _content_text(content: Any) -> str:
        if not isinstance(content, list):
            return ""
        texts = [
            item["text"]
            for item in content
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        ]
        return "\n".join(texts)
