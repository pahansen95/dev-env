"""Core domain models and utilities for MCP Project Integration

# Core Package Architecture

The core package implements fundamental domain models that define the architectural
foundation of Claude Code integration with MCP. It establishes clear boundaries
between business logic and infrastructure concerns through strategic layering.

## Domain Model Philosophy

The package distinguishes between two categories of components:

**Fundamental Domain Models**
These represent the core abstractions of our application, encoding business logic
and invariants without dependency on external systems:

- **Session** - Stateful development contexts tracking progress toward goals
- **Task** - Bounded transformations executed through Claude Code
- **PythonConfigSerializer** - Configuration as executable code philosophy

**Infrastructure Utilities**
These provide controlled interfaces to external systems, isolating implementation
details from business logic:

- **GitOperations** - Version control system integration
- **FileSystemOperations** - Safe file manipulation within project boundaries
- **SubprocessRunner** - Process execution with timeout and streaming

## Architectural Principles

**Separation of Concerns**
Business logic remains pure, with infrastructure dependencies injected through
clear interfaces. This enables testing domain models without external mocks.

**Safety by Design**
All operations enforce project boundaries through Git integration, preventing
accidental or malicious operations outside the repository scope.

**Human-Centric Persistence**
Python configuration files provide executable, debuggable state persistence
that developers can inspect and modify directly when needed.

## Integration Patterns

The package supports multiple integration approaches:

1. **Direct Domain Usage** - Import models for programmatic control
2. **MCP Tool Wrappers** - Thin protocol adapters over domain logic
3. **CLI Integration** - Command-line interfaces for developer workflows

This layered architecture ensures the core domain remains stable while
supporting diverse integration requirements.
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
