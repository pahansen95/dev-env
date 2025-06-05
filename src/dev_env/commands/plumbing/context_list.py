"""List all contexts."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.state import ContextManager


class ContextListCommand(PlumbingCommand):
  """List all registered contexts."""

  def execute(self, args) -> dict:
    """List all contexts and return their details."""
    manager = ContextManager()
    contexts = manager.list_contexts()

    return {
      "contexts": [
        {
          "id": context.id,
          "name": context.name,
          "path": str(context.path),
          "created_at": context.created_at,
          "last_used": context.last_used,
          "state": context.state,
        }
        for context in contexts
      ]
    }
