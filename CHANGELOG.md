# Changelog

All notable user-visible changes to this integration are documented here.

The project follows semantic versioning. GitHub releases are created only after
the release tag passes tests, coverage, Ruff, HACS validation, and hassfest.

## [0.4.0] - 2026-08-26

### Added

- Native read-only Home Assistant workout calendar backed by bounded exercise
  diary MCP reads.
- Optional per-habit 7-day and 30-day completion sensors.
- Optional per-habit completion streak sensors.
- Optional connection, last-successful-refresh, and failed-section diagnostics.
- Fixable Home Assistant repair flow that can disable only feature groups whose
  required MCP tools are unavailable.

### Changed

- Coordinator polling now skips sections without an enabled consuming entity.
- Habit history requests share bounded concurrency and hourly analytics caching.
- Habit analytics failures are isolated from each habit's current daily state.
- Documentation now distinguishes transient calendar/history reads from stored
  entity state.

## [0.3.1] - 2026-08-26

### Added

- Resilient polling and privacy-safe technical diagnostics.
- Expanded wrapper and time-zone regression coverage.

### Fixed

- Time-zone behavior in Home Assistant tests and release validation.

## [0.3.0] - 2026-08-26

### Added

- Aggregate goal and 30-day trend sensors.
- Safe diary update and delete actions using stable entry IDs.
- Read-only diary, search, workout-preset, and habit-history actions.
- HACS and hassfest release validation.

[0.4.0]: https://github.com/JensRudolph/sparkyfitness-custom-integration/releases/tag/v0.4.0
[0.3.1]: https://github.com/JensRudolph/sparkyfitness-custom-integration/releases/tag/v0.3.1
[0.3.0]: https://github.com/JensRudolph/sparkyfitness-custom-integration/releases/tag/v0.3.0
