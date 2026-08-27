# Home Assistant actions

[Documentation index](README.md) · [Entities](entities.md) · [Automation cookbook](automations.md)

Every action has a fixed, reviewed MCP mapping and native Home Assistant
selectors. The integration deliberately does not expose a generic action for
calling arbitrary MCP tools or actions.

## Action reference

| Home Assistant action | MCP mapping or behavior |
|---|---|
| `sparkyfitness.refresh` | coordinator refresh |
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
| `sparkyfitness.create_workout_preset` | exact exercise search, then `create_workout_preset` |
| `sparkyfitness.log_workout_preset` | `sparky_manage_exercise/log_workout_preset` |
| `sparkyfitness.set_goals` | `sparky_manage_goals/set_goals` |
| `sparkyfitness.log_habit` | `sparky_manage_habits/log_habit` |
| `sparkyfitness.start_fasting` | `sparky_manage_checkin/log_fasting` with `ACTIVE` status |
| `sparkyfitness.log_fasting_window` | `sparky_manage_checkin/log_fasting` with start/end |
| `sparkyfitness.list_food_diary` | `sparky_get_food_diary` |
| `sparkyfitness.search_food` | `sparky_search_foods` |
| `sparkyfitness.list_exercise_diary` | `sparky_get_exercise_diary` |
| `sparkyfitness.search_exercise` | `sparky_search_exercises` |
| `sparkyfitness.list_workout_presets` | `sparky_manage_exercise/get_workout_presets` |
| `sparkyfitness.list_habits` | `sparky_manage_habits/list_habits` |
| `sparkyfitness.get_habit_history` | `sparky_manage_habits/get_habit_history` |

The Home Assistant action UI is the authoritative field reference. It describes
every field and supplies appropriate number, date, time, select, boolean,
config-entry, and object selectors.

## Account selection

With exactly one loaded SparkyFitness entry, actions select it automatically.
With multiple entries, provide `config_entry_id`:

```yaml
action: sparkyfitness.log_water
data:
  config_entry_id: 01M0EXAMPLEENTRYID
  amount: 500
  unit: ml
```

The ID identifies the Home Assistant config entry, not the SparkyFitness user ID.

## Dates and time zones

When an action omits its date, the integration sends the `today` keyword. Each
SparkyFitness account can then resolve the date in that user's configured time
zone. Explicit timestamps are sent in the reviewed MCP field format.

## Refresh after writes

After a successful mutation, the integration invalidates any relevant slow cache
and requests an immediate coordinator refresh. Unrelated polling sections remain
isolated.

## Safe updates and deletion

Update and delete actions require an exact diary-entry UUID. Names are never
resolved or guessed for destructive operations. Deletion also requires:

```yaml
confirm: true
```

Use the read-only diary actions to obtain entry IDs. Action responses are
returned to the caller and are never copied into entity attributes.

## Food behavior

`log_food` logs a food already stored in the authenticated user's SparkyFitness
database. The integration does not silently select or create an item from an
external provider.

Update and delete operations distinguish supported food-entry types according
to the live action schema.

## Exercise behavior

`log_exercise` supports structured sets when advertised by the current MCP
schema. Set weights are kilograms, duration/rest values are seconds, and
distance is kilometers.

`create_workout_preset` searches every supplied exercise name. Each must resolve
to exactly one case-insensitive exact result. If any name is missing or
ambiguous, the preset is not created.

## Goals

The current upstream surface provides `set_goals`, not separate create/update
goal records. The integration exposes only that real capability.

## Habits

`log_habit` targets one exact habit UUID and refreshes both today's state and any
enabled cached analytics for that habit.

The `refresh` action invalidates the hourly habit catalog cache. Habits created
outside Home Assistant are therefore discovered immediately on the next manual
refresh and their dynamic entities are added without reloading the integration.

## Fasting

`start_fasting` first fetches the current fasting status and creates a new active
record only when none exists. Starts are serialized per config entry so two
concurrent Home Assistant calls cannot create overlapping active records.
`log_fasting_window` records a new completed or cancelled interval with explicit
start and end timestamps.

The current MCP does not expose an operation that ends or modifies the already
active record, so the integration does not provide a misleading `end_fasting`
action.

## Read-only action responses

Diary, search, preset, habit-list, and habit-history actions support response
data in Home Assistant. Their results can be consumed by scripts and automations
without becoming persistent entity attributes.

See the [automation cookbook](automations.md) for practical examples.
