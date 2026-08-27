# Security and privacy

[Documentation index](README.md) · [Architecture](architecture.md) · [Troubleshooting](troubleshooting.md)

Health data and API credentials are sensitive. The integration is designed
around a narrow, direct trust boundary:

```text
Home Assistant
      │
      │  Streamable HTTP MCP
      │  Authorization: Bearer <personal API key>
      ▼
Configured SparkyFitness /mcp endpoint
```

## What the integration does not use

- No LLM or Codex dependency at runtime.
- No cloud relay or integration-owned backend.
- No telemetry or analytics.
- No direct PostgreSQL access.
- No browser cookies or web-session impersonation.
- No web scraping.
- No private/internal REST fallback.
- No generic action that can invoke arbitrary discovered MCP tools.

## API-key handling

The key is stored in the Home Assistant config entry and is used only to create
the bearer authorization header for the configured endpoint.

It is never intentionally included in:

- Logs.
- Diagnostics.
- Entity state or attributes.
- Device information.
- Home Assistant action responses.
- Repair issues.

Treat Home Assistant config-entry storage and backups as sensitive because they
contain integration credentials.

## TLS

Certificate verification is enabled by default. Disabling it makes interception
of credentials and health data possible. The option exists for controlled test
environments and certificate troubleshooting, not as a recommended production
configuration.

Prefer a trusted certificate or an internal certificate authority installed in
the Home Assistant trust store.

## Diagnostic contents

Diagnostics contain technical metadata only:

- Hostname and MCP endpoint.
- Integration and advertised SparkyFitness version.
- Negotiated MCP protocol version.
- Discovered MCP tool names.
- Enabled feature groups and update interval.
- Last successful refresh time.
- Failed polling sections and latest technical exception class.

Diagnostics do not contain:

- API key or authorization header.
- Entity values.
- Food, exercise, check-in, or habit history.
- Calendar events.
- Other personal health records.

## Entity-state minimization

- Missing values remain unknown instead of being fabricated.
- Full diary and history payloads are not stored as entity attributes.
- Habit entities keep only current state, stable ID, and compact derived metrics.
- Calendar reads are transient and bounded to the requested range.
- Read-only action responses are returned only to the caller.

Home Assistant may record entity states according to the user's recorder
configuration. Review recorder exclusions and retention if even derived values
require tighter local retention.

## Mutation boundaries

Each write action maps to one reviewed MCP tool/action combination. Update and
delete operations require exact record IDs, and deletion requires explicit
confirmation. The integration does not infer a destructive target from a name.

Runtime tool discovery gates optional actions and entities, but discovery alone
does not authorize arbitrary tool execution.

## Reporting a security issue

Do not publish credentials or personal records in a GitHub issue. Revoke any key
that may have been exposed, create a replacement in SparkyFitness, and use Home
Assistant reauthentication to update it.
