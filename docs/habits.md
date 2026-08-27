# Habits

[Documentation index](README.md) · [Entities](entities.md) · [Actions](actions.md)

Habit support uses the reviewed actions exposed by `sparky_manage_habits`.
It does not require changes to the SparkyFitness MCP server.

## Habit catalog

The coordinator requests the authenticated user's boolean habit catalog and
caches it for one hour. A stable habit UUID is used for entity unique IDs, so a
rename updates the translated entity name without creating a duplicate.

`sparkyfitness.refresh` invalidates this catalog cache so externally created,
renamed, or removed habits can be synchronized immediately.

When an authoritative catalog refresh removes a habit, its dynamic Home
Assistant entities and entity-registry entries are removed.

## Daily binary sensor

Each habit receives an enabled-by-default binary sensor for today's state.

| Condition | Entity state |
|---|---|
| explicitly completed today | on |
| explicitly missed today | off |
| no entry today | off, with `logged_today: false` |
| today's request failed | unavailable; last value retained internally |

The sensor attributes include only the stable habit ID and whether today has a
record. Full habit history is never attached.

## Optional analytics

For every habit, three sensors are created disabled by default:

- Completion rate over the last 7 days.
- Completion rate over the last 30 days.
- Current completion streak in calendar days.

Enable only the metrics you need from the Home Assistant entity registry.
History polling starts only when at least one analytics entity for that habit is
enabled.

## Completion-rate denominator

Rates use only days explicitly present in the MCP history:

```text
completion rate = completed tracked days / all tracked days × 100
```

An absent day is not invented as a miss. The rate sensors expose
`completed_days` and `tracked_days` attributes so the denominator remains
auditable. With no tracked days in the requested window, the value is unknown.

## Streak calculation

The streak counts consecutive explicitly completed calendar days:

- If today has a history entry, the calculation starts today.
- If today has no entry yet, it may start yesterday.
- An explicit miss ends the streak.
- An absent earlier day also ends the streak; it is not silently filled.

The latest tracked date is exposed as compact metadata on the streak sensor.

## Polling and caching

- Today's state is requested only for enabled daily habit sensors.
- Analytics use a bounded 30-day history range.
- Analytics refresh at most hourly unless invalidated by `log_habit`.
- At most four habit-history calls run concurrently.
- Only derived rates, counts, streak, and latest-date metadata are cached.

## Failure isolation

A failed daily-history request affects only the corresponding habit's daily
sensor. A failed analytics request affects only that habit's analytics entities
and does not make today's binary sensor unavailable.

Authentication failure still triggers config-entry reauthentication.

## Log a habit

Use an exact habit UUID:

```yaml
action: sparkyfitness.log_habit
data:
  habit_id: "11111111-1111-1111-1111-111111111111"
  completed: true
```

The write invalidates cached analytics for that habit and requests an immediate
refresh.
