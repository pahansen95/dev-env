"""Core domain models and utilities for MCP Project Integration

This package contains fundamental domain models that define the core
abstractions of our application, along with utilities for external
system interactions.
"""

# Fundamental domain models
from .serialization import PythonConfigSerializer

# External system utilities
from .utils import (
  GitOperations,
  FileSystemOperations,
  SubprocessRunner,
  SubprocessResult,
)

__all__ = [
  # Domain models
  "PythonConfigSerializer",
  # Utilities
  "GitOperations",
  "FileSystemOperations",
  "SubprocessRunner",
  "SubprocessResult",
]
