"""Exceptions for the SparkyFitness integration."""

from __future__ import annotations


class SparkyFitnessError(Exception):
    """Base exception for SparkyFitness."""


class SparkyFitnessConnectionError(SparkyFitnessError):
    """Raised when the MCP endpoint cannot be reached."""


class SparkyFitnessAuthenticationError(SparkyFitnessError):
    """Raised when the API key is invalid or revoked."""


class SparkyFitnessSslError(SparkyFitnessConnectionError):
    """Raised when TLS certificate validation fails."""


class SparkyFitnessTimeoutError(SparkyFitnessConnectionError):
    """Raised when an MCP request times out."""


class SparkyFitnessMcpError(SparkyFitnessError):
    """Raised for a JSON-RPC or MCP protocol error."""


class SparkyFitnessToolError(SparkyFitnessMcpError):
    """Raised when a SparkyFitness MCP tool reports an error."""


class SparkyFitnessUnsupportedFeatureError(SparkyFitnessError):
    """Raised when the connected server does not expose a required tool."""
