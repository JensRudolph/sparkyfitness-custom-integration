# Architecture

[Documentation index](README.md) · [Security and privacy](security-and-privacy.md) · [Development](development.md)

## Runtime data flow

```text
Home Assistant
  ├── Config flow / options / reauthentication
  ├── DataUpdateCoordinator
  ├── Sensors, binary sensors, and calendar
  ├── Explicit Home Assistant actions
  └── Privacy-preserving diagnostics
             │
             ▼
  Direct Streamable HTTP MCP client
             │
             ▼
  Configured SparkyFitness /mcp endpoint
```

The integration speaks MCP JSON-RPC directly. It is not a wrapper around a
SparkyFitness REST API and does not involve an LLM.

## MCP transport

The asynchronous client uses Home Assistant's shared `aiohttp` session and
supports the MCP methods needed by the current stateless server:

- `initialize`
- `tools/list`
- `tools/call`
- JSON responses
- Streamable HTTP SSE responses
- Protocol and session headers
- Timeouts and explicit error mapping

The client retains a session ID when a server supplies one and sends MCP cleanup
without closing Home Assistant's shared session.

## Capability discovery

During setup, `tools/list` is the authoritative capability inventory. Tool name,
description, and input schema are retained in memory.

Feature groups, entities, and actions are gated by discovered tools. A missing
optional tool does not fail the entire integration. Managed tool actions are
checked against advertised action enums and discovery can be refreshed before a
write is rejected as unsupported.

## Config-entry isolation

Every Home Assistant config entry owns its own:

- API key.
- Normalized MCP endpoint and TLS policy.
- MCP client and discovered tool set.
- Data coordinator and caches.
- Virtual device and stable entity unique IDs.

This allows multiple users or servers without a global singleton.

## Coordinator sections

The coordinator groups related reads into independently handled sections:

- Health summary.
- Nutrition.
- Check-in.
- Fasting.
- Engagement streak.
- Goals.
- 30-day trends.
- Habits.

A failure in one optional section preserves successful results from the others.
If every requested section fails, Home Assistant receives a coordinator failure
and entities become unavailable without being overwritten with zero.

## Demand-aware polling

The initial refresh runs before platform entities are registered so Home
Assistant can discover the available data. After platform setup, each static
entity registers the coordinator sections it consumes.

On subsequent cycles, a section is requested only when at least one consuming
entity is enabled. Feature-group options remain the outer gate. This keeps a
disabled entity from causing otherwise unnecessary MCP traffic.

Goals are refreshed at most every 30 minutes and 30-day trends at most hourly,
unless a relevant write invalidates their cache.

## Habits

The catalog is cached for one hour. Today's histories and optional analytical
histories share a semaphore with a maximum of four concurrent requests.
Analytics use a bounded 30-day range and cache only compact derived values.

Catalog, daily state, and analytics failures are handled separately. See
[Habits](habits.md).

## Calendar

The calendar platform is intentionally independent from the regular coordinator.
Home Assistant range requests become bounded exercise-diary calls, while a
15-minute platform refresh keeps the active/next event current. See
[Workout calendar](workout-calendar.md).

## Services and refreshes

Home Assistant actions are registered once and resolve the intended loaded config
entry at call time. Every wrapper maps typed action data to a reviewed MCP tool.

Successful writes request an immediate refresh. Goal or habit writes also
invalidate only the relevant slow cache.

## Error mapping and recovery

- Authentication errors become config-entry reauthentication.
- Connection, SSL, timeout, MCP, tool, and unsupported-feature failures remain
  distinguishable.
- Partial coordinator failures are recorded by technical section name.
- Failure and recovery transitions are logged once without health values.
- The normal update interval provides automatic recovery.
