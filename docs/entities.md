# Entities

[Documentation index](README.md) · [Configuration](configuration.md) · [Actions](actions.md)

Entities are created only when their feature group is enabled and the required
tool was returned by MCP `tools/list`. Missing values remain unknown; they are
never estimated or replaced with zero.

Entity IDs shown here are representative. Home Assistant derives the final ID
from the device/account name and the translated entity name. Stable unique IDs
keep registry customizations intact across reloads and updates.

## Daily health and nutrition

| Entity suffix | Source | Unit | Default |
|---|---|---:|---|
| `weight` | health summary or check-in diary | kg | enabled |
| `steps_today` | check-in diary | steps | enabled |
| `calories_today` | nutrition daily total | kcal | enabled |
| `protein_today` | nutrition daily total | g | enabled |
| `carbs_today` | nutrition daily total | g | enabled |
| `fat_today` | nutrition daily total | g | enabled |
| `fiber_today` | nutrition daily total | g | disabled |
| `sugar_today` | nutrition daily total | g | disabled |
| `sodium_today` | nutrition daily total | mg | disabled |
| `potassium_today` | nutrition daily total | mg | disabled |
| `water_today` | health summary | ml | enabled |
| `sleep_duration` | check-in diary | h | enabled |
| `sleep_score` | check-in diary | score | enabled |
| `mood` | check-in diary | 1–10 | enabled |
| `body_fat` | check-in diary | % | enabled |
| `exercise_count_today` | health summary | count | enabled |
| `logging_streak` | logging-streak tool | days | enabled |

## Goals and progress

| Entity suffix | Meaning | Unit | Default |
|---|---|---:|---|
| `calorie_goal` | active calorie target | kcal | enabled |
| `protein_goal` | active protein target | g | enabled |
| `carbs_goal` | active carbohydrate target | g | enabled |
| `fat_goal` | active fat target | g | enabled |
| `water_goal` | active hydration target | ml | enabled |
| `calories_remaining` | non-negative target remainder | kcal | disabled |
| `protein_remaining` | non-negative target remainder | g | disabled |
| `carbs_remaining` | non-negative target remainder | g | disabled |
| `fat_remaining` | non-negative target remainder | g | disabled |
| `water_remaining` | non-negative target remainder | ml | disabled |
| `calories_progress` | current value / target | % | disabled |
| `protein_progress` | current value / target | % | disabled |
| `carbs_progress` | current value / target | % | disabled |
| `fat_progress` | current value / target | % | disabled |
| `water_progress` | current value / target | % | disabled |

Remaining and progress values are calculated locally only when both the current
value and a positive goal exist. They are not estimates.

## 30-day trends

| Entity suffix | Unit |
|---|---:|
| `food_days_logged_30d` | days |
| `avg_daily_calories_30d` | kcal |
| `avg_daily_protein_30d` | g |
| `workouts_30d` | count |
| `active_days_30d` | days |
| `exercise_calories_30d` | calories reported by the SparkyFitness exercise trend | kcal |
| `avg_mood_30d` | 1–10 |
| `avg_sleep_duration_30d` | h |
| `avg_sleep_score_30d` | score |
| `weight_entries_30d` | count |

These structured aggregate sensors are refreshed at most hourly unless their
cache is explicitly invalidated.

## Fasting

| Entity | Meaning | Unit |
|---|---|---:|
| `binary_sensor.…_fasting` | whether a fast is currently active | on/off |
| `fasting_elapsed` | time since the active fast started | s |
| `fasting_target_end` | calculated target timestamp for protocols such as `16:8` | timestamp |
| `fasting_remaining` | calculated time until the target | s |
| `fasting_progress` | calculated target progress | % |
| `binary_sensor.…_fasting_goal_reached` | whether target duration is reached | on/off |

Fasting calculations use the current MCP status and the protocol label. They do
not create or modify a fasting record.

## Habits

For every boolean habit returned by SparkyFitness, the integration creates a
daily binary sensor:

```text
binary_sensor.<account>_<habit_name>
```

It is on when the habit is explicitly completed today, off when explicitly
missed or not logged, and unavailable when today's history request failed.
Attributes distinguish an unlogged day from a failed request.

The habit catalog is cached for at most one hour. Calling
`sparkyfitness.refresh` invalidates that cache and immediately discovers habits
created outside Home Assistant.

The following per-habit sensors are disabled by default:

| Dynamic suffix | Meaning | Unit |
|---|---|---:|
| `<habit>_completion_7d` | completed / explicitly tracked days | % |
| `<habit>_completion_30d` | completed / explicitly tracked days | % |
| `<habit>_streak` | consecutive completed calendar days | days |

See [Habits](habits.md) for denominator, streak, caching, and failure behavior.

## Workout calendar

`calendar.<account>_workouts` presents exercise diary rows as read-only calendar
events. It exists only when the exercise feature is enabled and the dedicated
exercise-diary read tool is available.

See [Workout calendar](workout-calendar.md) for range and time-zone behavior.

## Optional diagnostic entities

These entities are disabled by default and contain technical state only:

| Entity suffix | Meaning |
|---|---|
| `connection` | whether the latest coordinator cycle succeeded |
| `last_successful_refresh` | timestamp of the latest successful data refresh |
| `failed_polling_sections` | number and technical names of degraded sections |

The connection diagnostic remains available during an outage so the failure is
represented as off. Diagnostic attributes contain exception class names, never
API keys or health values.

## Device registry

All entities belong to one virtual **SparkyFitness** device per config entry.

- Manufacturer: `SparkyFitness`
- Model: `MCP`
- Software version: value advertised during MCP initialization, when available
- Configuration URL: the configured MCP endpoint

An optional account name is included in the device name, which makes multiple
users on the same server easy to distinguish.

## Availability and retention

- A failed optional section does not discard data from successful sections.
- A complete communication failure marks coordinator entities unavailable while
  retaining their last state internally.
- Entities recover on the next successful update.
- Diary and history payloads are not copied into entity attributes.
- Habit entities retain only current state and compact derived metrics.
- Calendar reads are transient and bounded to the requested range.
