"""Engine-level exceptions. Kept framework-free so callers map them to HTTP/MCP errors."""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all engine errors."""


class ToolInputError(EngineError):
    """Raised when a tool receives structurally invalid input it cannot process."""
