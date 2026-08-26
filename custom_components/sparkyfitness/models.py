"""Data models for the SparkyFitness integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .api import SparkyFitnessMcpClient
    from .coordinator import SparkyFitnessCoordinator


@dataclass(frozen=True, slots=True)
class McpTool:
    """A tool discovered through MCP."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class SparkyFitnessData:
    """Coordinator data exposed to entities."""

    values: dict[str, Any] = field(default_factory=dict)
    fasting: dict[str, Any] | None = None
    section_errors: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SparkyFitnessRuntimeData:
    """Runtime objects owned by one Home Assistant config entry."""

    client: SparkyFitnessMcpClient
    coordinator: SparkyFitnessCoordinator
