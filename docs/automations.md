# Automation cookbook

[Documentation index](README.md) · [Action reference](actions.md) · [Entities](entities.md)

These examples are starting points. Replace entity IDs, account targets, values,
and conditions with ones appropriate for your installation.

## Send smart-scale weight to SparkyFitness

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

Consider adding a condition that ignores unchanged or implausible values for
your particular scale.

## Log water

```yaml
action: sparkyfitness.log_water
data:
  amount: 500
  unit: ml
```

## Log mood

```yaml
action: sparkyfitness.log_mood
data:
  mood: 8
  notes: "Very good day"
```

## Log sleep

```yaml
action: sparkyfitness.log_sleep
data:
  duration_minutes: 450
  bedtime: "2026-08-25T22:30:00+02:00"
  wake_time: "2026-08-26T06:00:00+02:00"
  source: "Home Assistant"
```

Use the current Home Assistant action UI to confirm the selectors and accepted
ranges for your installed integration version.

## Log a custom metric

The measurement category must already exist in SparkyFitness.

```yaml
action: sparkyfitness.log_custom_metric
data:
  name: "Resting Heart Rate"
  value: 58
  unit: bpm
```

## Log exercise sets

Set fields and allowed `set_type` values follow the current MCP schema. Weights
are kilograms, set duration/rest values are seconds, and distance is kilometers.

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

## Create a workout preset safely

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

## Log a daily habit

Use the stable habit UUID returned by `sparkyfitness.list_habits`:

```yaml
action: sparkyfitness.log_habit
data:
  habit_id: "11111111-1111-1111-1111-111111111111"
  completed: true
```

## Correct a diary entry

```yaml
action: sparkyfitness.update_food_entry
data:
  entry_id: "11111111-1111-1111-1111-111111111111"
  quantity: 1.5
  meal_type: dinner
```

Obtain the exact entry ID through `sparkyfitness.list_food_diary`. The
integration never guesses a record from a name.

## Permanently delete an entry

Deletion requires explicit confirmation:

```yaml
action: sparkyfitness.delete_exercise_entry
data:
  entry_id: "22222222-2222-2222-2222-222222222222"
  confirm: true
```

## Start a fast

Start a new active fast at the current Home Assistant time:

```yaml
action: sparkyfitness.start_fasting
data:
  fasting_type: "16:8"
```

`sparkyfitness.log_fasting_window` records a separate completed or cancelled
interval with explicit start and end timestamps. It cannot end or alter an
already active record because the current MCP has no such mutation action.

## Target one of several accounts

```yaml
action: sparkyfitness.log_water
data:
  config_entry_id: 01M0EXAMPLEENTRYID
  amount: 350
  unit: ml
```

The selector in Home Assistant's action editor is safer than typing the config
entry ID manually.

## Use read-only response data

Home Assistant supports action response variables. For example, a script can
request diary data without exposing it as an entity:

```yaml
sequence:
  - action: sparkyfitness.list_exercise_diary
    data:
      date: today
    response_variable: exercise_diary
  - action: system_log.write
    data:
      level: debug
      message: >
        Exercise diary response received: {{ exercise_diary is mapping }}
```

Avoid writing complete personal diary responses to production logs. This example
logs only whether a mapping was returned.
