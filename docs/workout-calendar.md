# Workout calendar

[Documentation index](README.md) · [Entities](entities.md) · [Security and privacy](security-and-privacy.md)

The integration provides a native, read-only Home Assistant calendar backed by
the existing `sparky_get_exercise_diary` MCP tool.

## When it appears

The calendar is created when:

- The exercise feature group is enabled.
- MCP `tools/list` advertises `sparky_get_exercise_diary`.

The exercise-count sensor can still work through the health summary when the
dedicated diary tool is absent; a missing calendar does not disable the whole
exercise feature group.

## Read-only behavior

The calendar never creates, updates, or deletes a workout. Use the explicit
exercise actions for mutations.

Home Assistant calendar range requests are translated to bounded MCP
`start_date` and `end_date` arguments. Full exercise history is not loaded into
the coordinator or copied into entity attributes.

## Events

Supported stable fields are projected as follows:

| Calendar field | Exercise diary value |
|---|---|
| Summary | exercise name |
| Start | explicit timestamp or entry date/time |
| End | explicit end time or positive duration |
| Description | notes, when present |
| UID | stable entry ID, when present |

An entry with only a date becomes an all-day event. A timed entry without a
positive duration receives a safe one-hour display duration. An invalid end time
that does not follow the start is clamped to one minute after the start so Home
Assistant receives a valid event.

Rows without enough date/time information are ignored instead of being guessed.

## Time zones

- Timestamps carrying an explicit UTC offset retain that offset.
- Naive timestamps and date/time pairs are interpreted in Home Assistant's
  configured time zone.
- The existing diary response has no separate SparkyFitness user-zone field, so
  the integration cannot infer a different account time zone.

## Refreshes

The calendar refreshes its active/next event every 15 minutes using a bounded
window from the previous day through the next 30 days. Opening or browsing a
calendar range triggers only the requested bounded diary read.

Calendar polling is independent from the coordinator's regular health polling.

## Errors

- Rejected authentication starts Home Assistant reauthentication.
- MCP and connection failures are exposed as translated Home Assistant errors.
- Malformed diary data fails the affected calendar request without corrupting
  coordinator-backed health entities.

## Privacy

Workout summaries and notes necessarily appear in calendar event data because
they are the content being requested. They are not placed in diagnostics or
coordinator entity attributes. Home Assistant's recorder may store calendar
entity state according to your own recorder configuration.
