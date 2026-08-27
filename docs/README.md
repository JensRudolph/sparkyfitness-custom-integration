# SparkyFitness integration documentation

This is the complete user and contributor documentation for the SparkyFitness
Home Assistant custom integration.

## Get started

1. [Install the integration and create an API key](installation.md).
2. [Configure the connection and feature groups](configuration.md).
3. Review the available [entities](entities.md) and [actions](actions.md).
4. Adapt an example from the [automation cookbook](automations.md).

## User guides

| Guide | Use it when you want to… |
|---|---|
| [Installation](installation.md) | install, update, or manually copy the integration |
| [Configuration](configuration.md) | connect an account, change options, or add another API key |
| [Entities](entities.md) | understand values, units, availability, and optional entities |
| [Actions](actions.md) | read or write SparkyFitness data from Home Assistant |
| [Automation cookbook](automations.md) | copy and adapt practical YAML examples |
| [Workout calendar](workout-calendar.md) | understand calendar ranges, refreshes, and time zones |
| [Habits](habits.md) | use daily habit entities and optional completion analytics |
| [Troubleshooting](troubleshooting.md) | diagnose setup, authentication, TLS, or capability problems |
| [Security and privacy](security-and-privacy.md) | review data flow, secret handling, and diagnostic contents |

## Technical references

| Reference | Contents |
|---|---|
| [Compatibility](compatibility.md) | verified MCP baseline and known upstream limitations |
| [Architecture](architecture.md) | transport, discovery, coordinator, polling, and recovery |
| [Development](development.md) | dependencies, tests, validation, and release workflow |
| [Changelog](../CHANGELOG.md) | user-visible changes by version |

## Scope

The integration communicates directly with the configured SparkyFitness MCP
endpoint. It deliberately does not use an LLM, scrape the web interface, connect
to PostgreSQL, use browser sessions, or call private REST APIs. Unsupported
upstream capabilities remain documented limitations instead of being simulated.
