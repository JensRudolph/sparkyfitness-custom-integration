# Development

[Documentation index](README.md) · [Architecture](architecture.md) · [Compatibility](compatibility.md)

## Repository layout

```text
custom_components/sparkyfitness/  Home Assistant integration
tests/                            mocked regression suite
docs/                             user and technical documentation
.github/workflows/                validation and release automation
```

## Environment

The project uses Python 3.14 and `uv` with a committed lock file.

```bash
uv sync --extra test --locked
```

Tests require no real SparkyFitness URL or API key.

## Quality checks

```bash
uv run ruff check custom_components tests
uv run ruff format --check custom_components tests
uv run pytest --cov=custom_components/sparkyfitness --cov-report=term-missing --cov-fail-under=80
```

Home Assistant's complete official test harness targets Linux. On native
Windows, platform-independent tests can run locally; GitHub Actions runs the
complete mocked suite. WSL is not required for normal repository development.

## Test scope

The regression suite covers:

- Config, options, reconfigure, and reauthentication flows.
- MCP initialization, discovery, JSON/SSE calls, sessions, errors, and timeouts.
- Wrapper tool/action mappings and reviewed arguments.
- Coordinator success, partial/total failure, recovery, and demand-aware polling.
- Time-zone defaults and fasting calculations.
- Habit catalog, analytics caching, denominators, concurrency, and recovery.
- Workout calendar parsing, bounded ranges, time zones, and error mapping.
- Privacy-safe diagnostics and Home Assistant repair flows.
- Read/write/update/delete action behavior and multiple-entry targeting.
- Manifest, version, HACS, and release metadata.

## Validation workflow

Every push and pull request runs:

1. Locked dependency installation.
2. Ruff linting.
3. The complete mocked test suite with at least 80% coverage.
4. HACS repository validation.
5. Home Assistant hassfest validation.

A scheduled run also detects ecosystem drift.

## Release workflow

1. Update the version consistently in `manifest.json`, `const.py`,
   `pyproject.toml`, and `uv.lock`.
2. Update [the changelog](../CHANGELOG.md) and relevant documentation.
3. Push the release candidate and wait for the Validate workflow.
4. Create a semantic tag such as `v0.4.0` only after validation succeeds.
5. Push the tag.

The Release workflow repeats tests, coverage, HACS, and hassfest validation,
verifies the tag matches the manifest version, and only then creates the GitHub
release.

## MCP changes are out of scope

This repository adapts to the MCP capabilities exposed by SparkyFitness. It does
not modify or patch the SparkyFitness MCP server. When upstream lacks a required
read or mutation capability, document the limitation and keep the integration
ready for a future advertised tool instead of inventing a workaround.

## Documentation changes

Keep the root README concise and user-facing. Put detailed behavior in the
matching page under `docs/`, and update cross-links in `docs/README.md` when a new
guide is added.

Screenshot assets belong in `docs/images/`. Screenshots must redact hostnames,
account names, entity values, API keys, diary contents, and other personal health
information unless synthetic demo data is used.
