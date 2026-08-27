# MCP compatibility and known limitations

[Documentation index](README.md) · [Architecture](architecture.md) · [Troubleshooting](troubleshooting.md)

## Verified baseline

Development was checked on 2026-08-26 against:

- The `CodeWithCJ/SparkyFitness` main branch at `fe2f466` (server package 1.6.3).
- Its stateless `POST /mcp` implementation using
  `StreamableHTTPServerTransport`, JSON responses, bearer authentication, and no
  generated session ID.
- A live authenticated SparkyFitness MCP exposing 36 normal-user tools.
- Read-only live calls for health summary, nutrition summary, daily report,
  exercise totals, check-in diary, fasting status, logging streak, goal snapshot,
  30-day trends, trend analysis, and profile preferences.

Only response shapes and types needed for development were retained during live
verification. No real credentials or personal health values are part of tests or
the repository.

SparkyFitness is actively developed. Runtime tool discovery protects optional
features from missing tools, but it cannot make an incompatible output shape
safe. Update both projects deliberately and review release notes.

## Why the integration uses a small direct MCP client

The official Python MCP SDK was evaluated. Its current v2 client uses its own
`httpx2` transport and a broad dependency graph. The current SparkyFitness server
uses a narrow stateless JSON transport, while Home Assistant requires shared
HTTP-session injection.

The integration therefore implements the required MCP JSON-RPC subset directly
on Home Assistant's shared `aiohttp` session. This remains MCP, not a private
SparkyFitness REST workaround.

## Known upstream limitations

### Check-in projection

Health-summary and reporting data are structured JSON, but daily check-in detail
is currently a documented Markdown projection. Steps, sleep, mood, and body-fat
parsing follows the verified upstream output. If that projection changes
incompatibly, affected values become unknown; the integration does not guess.

No current structured read tool returns today's biometrics, mood, and sleep
together. The parser is isolated so it can be replaced if upstream adds one.

### Food selection

`log_food` logs an item already stored in the authenticated user's SparkyFitness
database. External provider lookup requires deterministic user selection, so the
integration does not silently choose or create an external food.

### Custom metrics

`log_custom_metric` requires an existing custom measurement category.

### Sleep score writes

Although the check-in schema accepts a `sleep_score` field, the verified upstream
implementation does not store the supplied value. The Home Assistant action does
not expose a misleading sleep-score input.

### Goals

The current MCP provides `set_goals`, not separate create/update goal records.
Although its schema accepts a target `weight`, the verified implementation does
not persist it. The integration exposes neither invented goal actions nor a
misleading target-weight field.

### Ending an active fast

The upstream `log_fasting` action always creates a fasting record and cannot
update/end an existing one. The integration therefore rejects `start_fasting`
while a fast is already active, but it can still record separate completed or
cancelled windows. No misleading `end_fasting` action is exposed.

### Workout time zones

Exercise diary timestamps with an explicit offset retain it. Date-only or naive
workout times use Home Assistant's configured time zone because the diary output
has no separate user-zone field.

### Deliberately unsupported data

Medication, coaching, image analysis, and profile mutation are intentionally not
entities. Full food, exercise, and habit histories are not stored as entity
attributes. Calendar reads are bounded and habit entities keep only compact
derivatives.

## Protocol versions

The integration recognizes its tested MCP protocol versions and reports an
unverified version through Home Assistant repairs. An unverified version is a
warning, not permission to assume a private transport or bypass discovery.

## Reporting a compatibility regression

Include integration, Home Assistant, and advertised SparkyFitness versions,
negotiated MCP protocol version, discovered tool names, and the technical error
class. Redact credentials and personal records. See [Troubleshooting](troubleshooting.md).
