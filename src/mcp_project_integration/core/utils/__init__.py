"""External system utilities for MCP Project Integration

Provides wrappers and interfaces for interacting with external systems
including Git, filesystem operations, subprocess management, and logging.
"""

from .git import GitOperations
from .filesystem import FileSystemOperations
from .subprocess import SubprocessRunner, SubprocessResult
from .logging import add_file_logging, configure_console_logging

__all__ = [
  "GitOperations",
  "FileSystemOperations",
  "SubprocessRunner",
  "SubprocessResult",
  "add_file_logging",
  "configure_console_logging",
]
