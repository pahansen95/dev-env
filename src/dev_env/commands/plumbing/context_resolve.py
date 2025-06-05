"""Resolve a context from path or name."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.state import ContextManager


class ContextResolveCommand(PlumbingCommand):
  """Resolve a context from the current directory or by name."""

  def execute(self, args) -> dict:
    """Resolve context and return its details."""
    manager = ContextManager()
    resolver = ContextResolver(manager)

    # Get optional name argument
    name = getattr(args, "name", None)
    context = resolver.resolve(name)

    if not context:
      return {
        "error": "Context not found",
        "code": "CONTEXT_NOT_FOUND",
      }

    return {
      "id": context.id,
      "name": context.name,
      "path": str(context.path),
      "created_at": context.created_at,
      "last_used": context.last_used,
      "state": context.state,
    }
