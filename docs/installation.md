# Installation

[Documentation index](README.md) · [Configuration](configuration.md) · [Troubleshooting](troubleshooting.md)

## Requirements

- Home Assistant 2026.8.0 or newer (Python 3.14.2+).
- A current SparkyFitness release with its in-process Streamable HTTP MCP endpoint.
- A personal SparkyFitness API key.
- Network access from Home Assistant to the configured SparkyFitness host.

## Create an API key

In SparkyFitness, open **Settings → Developer & Integrations → API Key
Management** and create a personal API key. Treat it like a password.

The server authenticates MCP requests with a bearer header. Never paste the key
into YAML, issue reports, screenshots, or logs.

## Install with HACS

Until this repository is included in the HACS default catalog:

1. Open HACS in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/JensRudolph/sparkyfitness-custom-integration`.
4. Select **Integration** as the repository category.
5. Install **SparkyFitness**.
6. Restart Home Assistant.

After the restart, continue with [Configuration](configuration.md).

## Manual installation

Copy the complete directory:

```text
custom_components/sparkyfitness
```

to:

```text
/config/custom_components/sparkyfitness
```

The final manifest must therefore be located at:

```text
/config/custom_components/sparkyfitness/manifest.json
```

Restart Home Assistant after copying the files.

## Update

### HACS installation

1. Open HACS and check for updates.
2. Install the latest SparkyFitness integration release.
3. Restart Home Assistant.
4. Verify the integration version under **Settings → Devices & services**.

### Manual installation

Replace the complete `sparkyfitness` custom-component directory with the one
from the new release. Do not merge individual Python files from different
versions. Restart Home Assistant afterward.

Configuration entries and entity registry settings are retained during normal
updates.

## Remove

Remove every SparkyFitness config entry through **Settings → Devices & services**
before deleting the custom-component directory. Removing the Home Assistant
integration does not delete or modify records stored in SparkyFitness.

## Next steps

- [Configure one or more accounts](configuration.md)
- [Review available entities](entities.md)
- [Try a Home Assistant action](actions.md)
