"""Core domain models and utilities for MCP Project Integration

This package contains fundamental domain models that define the core
abstractions of our application, along with utilities for external
system interactions.
"""

# Fundamental domain models
from .serialization import PythonConfigSerializer
from .session import Session, Task

# Project utilities
from .project import find_git_root, get_git_project_name, get_safe_path

# External system utilities
from .utils import (
  GitOperations,
  FileSystemOperations,
  SubprocessRunner,
  SubprocessResult,
  add_file_logging,
  configure_console_logging,
)

__all__ = [
  # Domain models
  "PythonConfigSerializer",
  "Session",
  "Task",
  # Project utilities
  "find_git_root",
  "get_git_project_name",
  "get_safe_path",
  # Logging utilities
  "add_file_logging",
  "configure_console_logging",
  # External utilities
  "GitOperations",
  "FileSystemOperations",
  "SubprocessRunner",
  "SubprocessResult",
]
