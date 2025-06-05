"""Get environment status."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager, StateManager


class EnvStatusCommand(PlumbingCommand):
  """Get current environment status."""

  def execute(self, args) -> dict:
    """Get environment status and return details."""
    # Resolve context
    context_manager = ContextManager()
    resolver = ContextResolver(context_manager)
    context_name = getattr(args, "context", None)
    context = resolver.resolve(context_name)

    if not context:
      return {
        "error": "Context not found",
        "code": "CONTEXT_NOT_FOUND",
      }

    # Get environment state
    state_manager = StateManager(context_manager.state_dir)
    env_state = state_manager.get_environment(context.name)

    if not env_state:
      return {
        "name": context.name,
        "state": "notfound",
        "context_id": context.id,
        "context_state": context.state,
      }

    # Check actual container state
    try:
      docker = DockerClient()
      container_id = env_state["container_id"]

      try:
        container_info = docker.inspect_container(container_id)
        container_exists = True
        container_running = container_info.get("State", {}).get("Running", False)
      except Exception:
        container_exists = False
        container_running = False

      state = "running" if container_running else "stopped" if container_exists else "notfound"

      return {
        "name": context.name,
        "container_id": env_state["container_id"],
        "container_name": env_state["container_name"],
        "state": state,
        "context_id": context.id,
        "context_state": context.state,
        "created_at": env_state["created_at"],
        "updated_at": env_state["updated_at"],
      }
    except Exception as e:
      return {
        "error": str(e),
        "code": "STATUS_FAILED",
      }
