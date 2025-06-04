"""External system utilities for MCP Project Integration

Provides wrappers and interfaces for interacting with external systems
including Git, filesystem operations, and subprocess management.
"""

from .git import GitOperations
from .filesystem import FileSystemOperations
from .subprocess import SubprocessRunner, SubprocessResult

__all__ = [
  "GitOperations",
  "FileSystemOperations",
  "SubprocessRunner",
  "SubprocessResult",
]
