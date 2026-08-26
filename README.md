# SparkyFitness for Home Assistant

A privacy-conscious Home Assistant custom integration that connects directly to a
self-hosted [SparkyFitness](https://github.com/CodeWithCJ/SparkyFitness) instance
through its Model Context Protocol (MCP) endpoint.

The integration reads current health and fitness data into Home Assistant and
provides explicit actions for writing data back. It does not use an LLM, a cloud
relay, private REST endpoints, database access, browser cookies, or web scraping.

```text
Home Assistant
  ├── Config flow / options / reauthentication
  ├── DataUpdateCoordinator
  ├── Sensors and fasting binary sensor
  ├── Explicit Home Assistant actions
  └── Privacy-preserving diagnostics
             │
             ▼
  Direct Streamable HTTP MCP client
             │
             ▼
  https://your-sparkyfitness-host/mcp
```

## Features

- UI-only connection setup; no YAML credentials.
- Direct asynchronous MCP transport using Home Assistant's shared `aiohttp`
  session.
- Bearer API-key authentication and TLS certificate verification by default.
- MCP `initialize`, `tools/list`, `tools/call`, JSON responses, Streamable HTTP
  SSE responses, protocol/session headers, timeouts, and explicit error mapping.
- Runtime tool discovery: optional features disappear cleanly when a server does
  not expose their tool.
- Five-minute coordinated polling by default, configurable from 1–60 minutes.
- Independent polling sections: a check-in failure does not discard valid
  nutrition or engagement data.
- Current goal sensors and structured 30-day aggregate sensors, with slower
  polling for those more expensive data sets.
- ID-scoped update/delete actions for food and exercise diary entries, with an
  explicit confirmation field for permanent deletion.
- Multiple SparkyFitness accounts/instances. Actions automatically target the
  only loaded entry, or accept `config_entry_id` when several entries exist.
- API-key reauthentication without deleting the config entry.
- English and German UI/entity translations.
- HACS-ready repository layout and manual installation support.

## Requirements

- Home Assistant 2026.8.0 or newer (Python 3.14.2+).
- A current SparkyFitness release with its in-process Streamable HTTP MCP endpoint.
- A personal SparkyFitness API key.
- Network access from Home Assistant to the configured SparkyFitness host.

## Create an API key

In SparkyFitness, open **Settings → Developer & Integrations → API Key
Management** and create a personal API key. Treat it like a password.

The server authenticates MCP requests with:

```http
Authorization: Bearer <API_KEY>
```

## Installation

### HACS

Until this repository is included in the HACS default catalog:

1. Open HACS in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add this repository URL and select **Integration**.
4. Install **SparkyFitness**.
5. Restart Home Assistant.

### Manual installation

Copy the complete directory:

```text
custom_components/sparkyfitness
```

to:

```text
/config/custom_components/sparkyfitness
```

Restart Home Assistant after copying or updating it.

## Configuration

1. Go to **Settings → Devices & services**.
2. Select **Add integration** and search for **SparkyFitness**.
3. Enter either the base URL, such as
   `https://sparkyfitness.example.com`, or the complete endpoint,
   `https://sparkyfitness.example.com/mcp`.
4. Enter the personal API key.
5. Keep TLS verification enabled.

Before creating the entry, the flow initializes MCP, requests `tools/list`, and
requires at least one characteristic SparkyFitness tool. It distinguishes
connection, authentication, non-MCP, TLS, and timeout failures.

### Options

Open the integration's **Configure** dialog to change:

- Update interval: 1–60 minutes (default: 5).
- TLS certificate verification.
- Nutrition sensors.
- Exercise sensors.
- Check-in sensors.
- Engagement sensors.
- Goal sensors.
- 30-day trend sensors.

Disabling a feature group also prevents its unnecessary MCP polling calls.
Disabling TLS verification is unsafe: it allows interception of both the API key
and sensitive health data.

## Entities

Entities are created only when their required tool was returned by `tools/list`.
Missing data remains unknown; it is never estimated or replaced with zero.

| Entity suffix | Source | Unit |
|---|---|---|
| `weight` | `sparky_get_health_summary` / check-in diary | kg |
| `steps_today` | `sparky_manage_checkin/list_checkin_diary` | steps |
| `calories_today` | `sparky_get_health_summary` | kcal |
| `protein_today` | `sparky_get_health_summary` | g |
| `carbs_today` | `sparky_get_health_summary` | g |
| `fat_today` | `sparky_get_health_summary` | g |
| `water_today` | `sparky_get_health_summary` | ml |
| `sleep_duration` | `sparky_manage_checkin/list_checkin_diary` | h |
| `sleep_score` | `sparky_manage_checkin/list_checkin_diary` | score |
| `mood` | `sparky_manage_checkin/list_checkin_diary` | 1–10 |
| `body_fat` | `sparky_manage_checkin/list_checkin_diary` | % |
| `exercise_count_today` | `sparky_get_health_summary` | count |
| `logging_streak` | `sparky_get_logging_streak` | days |
| `calorie_goal` | `sparky_get_goal_snapshot` | kcal |
| `protein_goal` | `sparky_get_goal_snapshot` | g |
| `carbs_goal` | `sparky_get_goal_snapshot` | g |
| `fat_goal` | `sparky_get_goal_snapshot` | g |
| `water_goal` | `sparky_get_goal_snapshot` | ml |
| `food_days_logged_30d` | `sparky_get_30_day_trends` | days |
| `avg_daily_calories_30d` | `sparky_get_30_day_trends` | kcal |
| `avg_daily_protein_30d` | `sparky_get_30_day_trends` | g |
| `workouts_30d` | `sparky_get_30_day_trends` | count |
| `active_days_30d` | `sparky_get_30_day_trends` | days |
| `exercise_calories_30d` | `sparky_get_30_day_trends` | kcal |
| `avg_mood_30d` | `sparky_get_30_day_trends` | 1–10 |
| `avg_sleep_duration_30d` | `sparky_get_30_day_trends` | h |
| `avg_sleep_score_30d` | `sparky_get_30_day_trends` | score |
| `weight_entries_30d` | `sparky_get_30_day_trends` | count |
| `binary_sensor.sparkyfitness_fasting` | `sparky_manage_checkin/get_fasting_status` | on/off |

All entities belong to one virtual **SparkyFitness** device per config entry. The
MCP server version from the initialize response is shown as the software version
when available.

## Actions

Every action uses a fixed, reviewed MCP mapping. There is deliberately no generic
“call any MCP tool” action.

| Home Assistant action | MCP mapping |
|---|---|
| `sparkyfitness.refresh` | Coordinator refresh |
| `sparkyfitness.log_weight` | `sparky_manage_checkin/log_biometrics` |
| `sparkyfitness.log_biometrics` | `sparky_manage_checkin/log_biometrics` |
| `sparkyfitness.log_water` | `sparky_manage_food/log_water` |
| `sparkyfitness.log_mood` | `sparky_manage_checkin/log_mood` |
| `sparkyfitness.log_sleep` | `sparky_manage_checkin/log_sleep` |
| `sparkyfitness.log_custom_metric` | `sparky_manage_checkin/log_custom_metric` |
| `sparkyfitness.log_food` | `sparky_manage_food/log_food` |
| `sparkyfitness.update_food_entry` | `sparky_manage_food/update_entry` by entry ID |
| `sparkyfitness.delete_food_entry` | `sparky_manage_food/delete_entry` by entry ID |
| `sparkyfitness.log_exercise` | `sparky_manage_exercise/log_exercise` |
| `sparkyfitness.update_exercise_entry` | `sparky_manage_exercise/update_exercise_entry` by entry ID |
| `sparkyfitness.delete_exercise_entry` | `sparky_manage_exercise/delete_exercise_entry` by entry ID |
| `sparkyfitness.create_exercise` | `sparky_manage_exercise/create_exercise` |
| `sparkyfitness.create_workout_preset` | search, then `create_workout_preset` |
| `sparkyfitness.log_workout_preset` | `sparky_manage_exercise/log_workout_preset` |
| `sparkyfitness.set_goals` | `sparky_manage_goals/set_goals` |
| `sparkyfitness.log_habit` | `sparky_manage_habits/log_habit` |
| `sparkyfitness.start_fasting` | `sparky_manage_checkin/log_fasting` with `ACTIVE` status |
| `sparkyfitness.log_fasting_window` | `sparky_manage_checkin/log_fasting` with start/end |

After every successful write, the coordinator requests an immediate refresh.
All action fields and selectors are documented in the Home Assistant action UI.

Update and delete actions deliberately require an exact diary-entry UUID. Delete
actions additionally require `confirm: true`; names are never resolved or guessed
for destructive operations. IDs are shown by the corresponding SparkyFitness food
or exercise diary MCP output.

If multiple SparkyFitness config entries are loaded, add the optional
`config_entry_id` field. With exactly one loaded entry, it is selected
automatically.

## Automation examples

### Send smart-scale weight to SparkyFitness

```yaml
automation:
  - alias: "Weight to SparkyFitness"
    triggers:
      - trigger: state
        entity_id: sensor.smart_scale_weight

    conditions:
      - condition: template
        value_template: >
          {{ trigger.to_state.state not in ['unknown', 'unavailable'] }}

    actions:
      - action: sparkyfitness.log_weight
        data:
          weight: "{{ trigger.to_state.state | float }}"
          unit: kg
```

### Log water

```yaml
action: sparkyfitness.log_water
data:
  amount: 500
  unit: ml
```

### Log mood

```yaml
action: sparkyfitness.log_mood
data:
  mood: 8
  notes: "Very good day"
```

### Log a custom metric

The category must already exist in SparkyFitness.

```yaml
action: sparkyfitness.log_custom_metric
data:
  name: "Resting Heart Rate"
  value: 58
  unit: bpm
```

### Log exercise sets

Set field names and allowed `set_type` values match the current MCP schema.
Weights are kilograms, set duration/rest values are seconds, and distance is km.

```yaml
action: sparkyfitness.log_exercise
data:
  exercise: "Bench Press"
  notes: "Good session"
  sets:
    - reps: 10
      weight: 80
      set_type: "Working Set"
      rpe: 8
    - reps: 9
      weight: 80
      set_type: "Working Set"
      rpe: 9
    - reps: 8
      weight: 80
      set_type: "Working Set"
      rpe: 9
```

### Create a workout preset safely

```yaml
action: sparkyfitness.create_workout_preset
data:
  name: "Push A"
  exercises:
    - "Bench Press"
    - "Incline Dumbbell Bench Press"
    - "Lateral Raise"
    - "Triceps Pushdown"
```

Every name must resolve to exactly one case-insensitive exact search result. If a
name is missing or ambiguous, nothing is created.

### Correct or delete an exact diary entry

```yaml
action: sparkyfitness.update_food_entry
data:
  entry_id: "11111111-1111-1111-1111-111111111111"
  quantity: 1.5
  meal_type: dinner
```

Permanent deletion requires an explicit confirmation:

```yaml
action: sparkyfitness.delete_exercise_entry
data:
  entry_id: "22222222-2222-2222-2222-222222222222"
  confirm: true
```

### Start or record fasting

Start a new active fast at the current Home Assistant time:

```yaml
action: sparkyfitness.start_fasting
data:
  fasting_type: "16:8"
```

`sparkyfitness.log_fasting_window` records a new completed or cancelled interval
with explicit start and end timestamps. It does not end or alter an already active
fast; the current MCP has no mutation action for that operation.

## Data updates and availability

The coordinator uses a single health-summary request for nutrition, hydration,
weight, and exercise totals. Check-in, fasting, and streak sections are fetched
only when their tools and feature groups are active. Goals are refreshed at most
every 30 minutes and 30-day aggregates at most hourly, unless a relevant write or
manual refresh invalidates that cache.

Optional section errors are isolated. A total communication failure marks
coordinator entities unavailable while retaining their last state. The next
successful poll recovers automatically. A rejected/revoked API key starts Home
Assistant's reauthentication flow.

## Diagnostics and security

Diagnostics contain only technical metadata:

- Hostname and MCP endpoint.
- Integration and advertised SparkyFitness version.
- Discovered tool names.
- Enabled feature groups and update interval.
- Last successful refresh time and last technical exception class.

Diagnostics never contain the API key, authorization header, entity values,
food diary, exercise diary, or other health records. The API key is never logged
or exposed as an entity attribute. There is no telemetry or analytics.

Communication is exclusively:

```text
Home Assistant ↔ configured SparkyFitness MCP endpoint
```

## Troubleshooting

### Cannot connect

- Confirm Home Assistant can resolve and reach the SparkyFitness hostname.
- Confirm the endpoint is `/mcp`; a base URL is normalized automatically.
- Check reverse-proxy routing for `POST /mcp`.
- Confirm the server is a current release with the in-process MCP endpoint.

### Invalid authentication

Create a new personal API key in SparkyFitness and complete the reauthentication
flow in Home Assistant. Do not delete the integration.

### TLS error

Install a certificate trusted by the Home Assistant host. Disabling verification
is available only as an explicit unsafe option.

### An entity is missing

Check diagnostics for the corresponding tool. Optional entities are not created
when `tools/list` does not advertise the required capability, or when their
feature group is disabled.

### An action reports “unsupported feature”

The configured SparkyFitness release did not advertise the required MCP tool.
Upgrade SparkyFitness; the integration does not fall back to private APIs.

## Known limitations

- The current MCP returns health-summary and reporting data as JSON, but the
  daily check-in detail as a documented Markdown projection. Steps, sleep, mood,
  and body-fat parsing follows the current upstream implementation and live MCP
  output. If that projection changes incompatibly, those values become unknown;
  the integration does not guess.
- `log_food` logs foods already stored in the authenticated user's SparkyFitness
  database. External provider lookup requires a deterministic user selection, so
  this integration does not silently choose or create an external food.
- `log_custom_metric` requires an existing custom measurement category.
- Although the current check-in schema accepts a `sleep_score` write field, the
  upstream implementation does not store that supplied value. The Home Assistant
  action therefore does not expose a misleading sleep-score input.
- The current MCP has `set_goals`; it does not expose distinct create/update goal
  records. The integration implements the real action as `set_goals` instead of
  inventing `create_goal` or `update_goal`.
- The current `log_fasting` MCP action always creates a fasting record. It can
  start a new active fast or record a completed window, but it cannot update/end
  the already active record. No misleading `end_fasting` action is exposed.
- No current MCP read tool returns today's biometrics, mood, and sleep together as
  structured JSON. Priority check-in sensors therefore still use the upstream
  Markdown projection; the isolated parser can be replaced when such a tool is
  added upstream.
- Medication, coaching, image-analysis, profile mutation, and full diary/history
  payloads are intentionally not entities or generic actions in this release.

## MCP compatibility verification

Development was checked on 2026-08-26 against:

- The `CodeWithCJ/SparkyFitness` main branch at `fe2f466` (server package 1.6.3).
- Its stateless `POST /mcp` implementation using
  `StreamableHTTPServerTransport`, JSON responses, bearer authentication, and
  no generated session ID.
- A live authenticated SparkyFitness MCP exposing 36 normal-user tools.
- Read-only live calls for health summary, nutrition summary, daily report,
  exercise totals, check-in diary, fasting status, logging streak, goal snapshot,
  30-day trends, trend analysis, and profile preferences. Only shapes/types were
  retained during verification.

The official Python MCP SDK was also evaluated. Its current v2 client uses its
own `httpx2` transport and a broad dependency graph. SparkyFitness's current
stateless JSON transport needs only the standard MCP methods used here, while
Home Assistant requires shared HTTP-session injection. The integration therefore
implements this small MCP subset directly on Home Assistant's `aiohttp` session;
it is still MCP JSON-RPC, not a SparkyFitness REST workaround.

## Development

```bash
uv sync --extra test
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run pytest
```

Home Assistant's official test harness targets Linux. On Windows, run the suite
inside WSL, a Linux container, or Home Assistant's development container.

The tests use mocks only and require no real SparkyFitness URL or API key. They
cover config flow errors, MCP discovery/calls/errors/timeouts/disconnect/reconnect,
coordinator partial/total failure, slow-section throttling and recovery, privacy
diagnostics, output parsing, and the key write/update/delete actions.

## License

[MIT](LICENSE)
