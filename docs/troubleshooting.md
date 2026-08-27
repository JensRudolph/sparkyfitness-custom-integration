# Troubleshooting

[Documentation index](README.md) · [Configuration](configuration.md) · [Compatibility](compatibility.md)

## Cannot connect

- Confirm Home Assistant can resolve and reach the SparkyFitness hostname.
- Confirm the endpoint is `/mcp`; a base URL is normalized automatically.
- Check reverse-proxy routing for `POST /mcp`.
- Confirm the server is a current release with the in-process MCP endpoint.
- If Home Assistant runs in a container, test connectivity from that network,
  not only from a desktop browser.

The setup flow distinguishes connection failure, timeout, invalid MCP response,
TLS failure, and unexpected errors.

## Invalid authentication

Create a new personal API key in SparkyFitness and complete Home Assistant's
reauthentication flow. Do not delete the integration.

Check that the key belongs to the intended SparkyFitness user. Each Home
Assistant config entry stores exactly one personal key.

## TLS error

Install a certificate trusted by the Home Assistant host and include all
intermediate certificates. A certificate accepted by a desktop browser may
still be untrusted inside the Home Assistant container or operating system.

Disabling certificate verification is available as an explicit unsafe option.
Use it only temporarily in a controlled network.

## The repository returns 404 in HACS

Use the repository URL, not the GitHub API URL:

```text
https://github.com/JensRudolph/sparkyfitness-custom-integration
```

Select **Integration** as the custom-repository category. Confirm the repository
is reachable without a GitHub login and then reload HACS.

## The integration does not appear after installation

- Restart Home Assistant after installing or updating a custom integration.
- Confirm `manifest.json` is located at
  `/config/custom_components/sparkyfitness/manifest.json`.
- Check Home Assistant logs for a manifest or import error.
- Do not nest an extra repository directory below `custom_components`.

## An entity is missing

An entity is created only when all of these are true:

- Its feature group is enabled in the integration options.
- The connected MCP advertises the required tool.
- For dynamic entities, the source habit exists in the current catalog.

Some entities are present but disabled by default. Check the device's complete
entity list and enable them in the entity registry.

Use integration diagnostics to inspect discovered tool names without exposing
health values.

## An action reports “unsupported feature”

The configured SparkyFitness release did not advertise the required MCP tool or
action. Upgrade SparkyFitness if a later upstream version provides it. The
integration does not fall back to private APIs.

Tool/action schemas are checked again when an advertised action appears to have
changed, which prevents stale discovery metadata from causing a blind write.

## Values are unknown

Unknown is different from zero. Common causes are:

- No source value has been recorded for the current date.
- The upstream response omitted the value.
- A source projection changed and could not be parsed safely.
- A goal-dependent sensor has no current value or no positive goal.

The integration deliberately does not estimate missing health data.

## Entities are unavailable

Open the optional connection and failed-section diagnostics. A partial outage
can affect one data section while other entities remain available. A total
communication failure makes coordinator-backed entities unavailable until a
successful retry.

The coordinator retries automatically at the configured interval. Use
`sparkyfitness.refresh` after repairing the connection if you do not want to
wait for the next cycle.

## Habit analytics do not update

- Analytics entities are disabled by default; enable at least one for the habit.
- Analytics refresh at most hourly unless invalidated by `log_habit`.
- Check whether the analytics entity is unavailable while the daily habit sensor
  remains healthy; failures are intentionally isolated.
- Completion rates use explicit tracked days only, so an empty range is unknown.

## Workout calendar is missing or empty

- Enable the exercise feature group.
- Confirm diagnostics list `sparky_get_exercise_diary`.
- Browse a range that contains recorded exercise entries.
- Check Home Assistant's configured time zone for date-only or naive diary times.

The calendar is read-only and performs bounded range requests; it does not load
all historical workouts during coordinator refreshes.

## Repair issues

Home Assistant may report:

- Authentication failure: complete reauthentication.
- Unsupported protocol: update the integration or use a verified server version.
- Missing tools: update SparkyFitness or run the fix flow to disable only the
  affected local feature groups.

The missing-tool fix flow changes only Home Assistant config-entry options. It
does not modify the SparkyFitness MCP server.

## Information to include in a bug report

- Integration version and Home Assistant version.
- SparkyFitness version advertised in diagnostics.
- Negotiated MCP protocol version.
- Discovered tool names and failed technical sections.
- Exact reproduction steps and the relevant technical error class.

Do not include API keys, authorization headers, full diagnostics from unrelated
integrations, diary contents, or personal health values.
