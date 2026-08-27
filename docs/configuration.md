# Configuration

[Documentation index](README.md) · [Installation](installation.md) · [Entities](entities.md)

## Add an account

1. Go to **Settings → Devices & services**.
2. Select **Add integration** and search for **SparkyFitness**.
3. Enter either the base URL, such as `https://sparkyfitness.example.com`, or
   the complete endpoint, `https://sparkyfitness.example.com/mcp`.
4. Optionally enter an account name such as `Jens`.
5. Enter the personal API key.
6. Keep TLS verification enabled.

The flow normalizes a base URL to `/mcp`, initializes MCP, requests `tools/list`,
and requires at least one characteristic SparkyFitness tool. Connection,
authentication, non-MCP, TLS, timeout, and unexpected errors are reported
separately.

## Options

Open the integration's **Configure** dialog to change:

- Update interval: 1–60 minutes (default: 5).
- Account name used in config-entry and device names.
- TLS certificate verification.
- Nutrition sensors.
- Exercise sensors.
- Check-in sensors.
- Engagement sensors.
- Goal sensors.
- 30-day trend sensors.
- Habit sensors.

Disabling a feature group prevents its unnecessary MCP polling. Within an
enabled group, polling sections without an enabled consuming entity are skipped
after the initial setup refresh.

> [!WARNING]
> Disabling TLS verification permits interception of both the API key and
> sensitive health data. Use it only for a controlled test environment while
> repairing certificate trust.

## Change the URL or TLS policy

Use the integration's **Reconfigure** action to change the MCP URL or TLS policy.
The existing API key is validated against the new endpoint before the config
entry is updated and reloaded. Stable entity unique IDs are retained.

## Multiple users, instances, or API keys

Create one Home Assistant config entry per personal API key. Entries do not share
clients, coordinator state, devices, or credentials.

Multiple keys can point to the same SparkyFitness server. Give each entry a clear
account name so its virtual device and config entry remain distinguishable.

When exactly one entry is loaded, actions select it automatically. With multiple
entries, supply the optional `config_entry_id` field in the action data. Home
Assistant's action UI provides the appropriate config-entry selector.

## Entity creation and optional entities

Entities are created only when the relevant feature group is enabled and the
required MCP tool is advertised by `tools/list`. Some less commonly used or
technical entities are created disabled by default. Enable them from the entity
registry when needed.

This includes:

- Goal progress and remaining-amount sensors.
- Fiber, sugar, sodium, and potassium sensors.
- Per-habit 7/30-day completion and streak sensors.
- Connection, last-successful-refresh, and failed-section diagnostics.

## Reauthentication

If SparkyFitness rejects or revokes an API key, Home Assistant starts a
reauthentication flow. Enter a new key there; deleting and recreating the
integration is not necessary.

## Repairs

Home Assistant can create repair issues for:

- Rejected authentication.
- An unverified MCP protocol version.
- Tools missing from enabled feature groups.

The missing-tool repair can disable only the affected local feature switches and
reload the entry after confirmation. It never changes SparkyFitness or the MCP
server.
