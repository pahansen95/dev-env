"""Create a new context."""

from pathlib import Path

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.state import ContextManager


class ContextCreateCommand(PlumbingCommand):
  """Create a new context."""

  def execute(self, args) -> dict:
    """Create a new context and return its details."""
    name = args.name
    path = Path(args.path) if hasattr(args, "path") and args.path else Path.cwd()

    # Ensure path exists
    if not path.exists():
      return {
        "error": f"Path does not exist: {path}",
        "code": "PATH_NOT_FOUND",
      }

    # Create .dev-env directory
    dev_env_dir = path / ".dev-env"
    dev_env_dir.mkdir(exist_ok=True)

    # Create context
    try:
      manager = ContextManager()
      context = manager.create_context(name, path)

      return {
        "id": context.id,
        "name": context.name,
        "path": str(context.path),
        "created_at": context.created_at,
        "state": context.state,
      }
    except Exception as e:
      if "UNIQUE constraint failed" in str(e):
        return {
          "error": f"Context with name '{name}' already exists",
          "code": "CONTEXT_EXISTS",
        }
      raise
