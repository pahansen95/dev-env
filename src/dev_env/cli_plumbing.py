"""Base class for plumbing commands that output JSON."""

import json
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict


class PlumbingCommand(ABC):
  """Base class for all plumbing commands."""

  @abstractmethod
  def execute(self, args) -> Dict[str, Any]:
    """Execute the command and return JSON-serializable dict."""
    raise NotImplementedError

  def output(self, result: Dict[str, Any]) -> None:
    """Output JSON to stdout."""
    json.dump(result, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()

  def run(self, args) -> None:
    """Run the command and output the result."""
    try:
      result = self.execute(args)
      self.output(result)
    except Exception as e:
      error_result = {
        "error": str(e),
        "code": e.__class__.__name__,
      }
      self.output(error_result)
      sys.exit(1)
