"""Base command interface for consistent error handling and testing."""

import sys
from abc import ABC, abstractmethod
from typing import Any

from .utils import DevEnvError


class BaseCommand(ABC):
  """Base class for all dev-env commands providing consistent interface."""

  def execute(self, args: Any) -> int:
    """Execute command and return exit code.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
      self._run(args)
      return 0
    except DevEnvError as e:
      self._handle_error(e)
      return e.exit_code
    except Exception as e:
      # Unexpected errors become generic DevEnvError
      error = DevEnvError(f"Unexpected error: {e}")
      self._handle_error(error)
      return error.exit_code

  @abstractmethod
  def _run(self, args: Any) -> None:
    """Execute the command logic.

    Override in subclasses with pure business logic.
    Should raise DevEnvError subclasses for known error conditions.
    """
    pass

  def _handle_error(self, error: DevEnvError) -> None:
    """Handle error display to user.

    Can be overridden for custom error formatting.
    """
    print(error.format_error(), file=sys.stderr)
