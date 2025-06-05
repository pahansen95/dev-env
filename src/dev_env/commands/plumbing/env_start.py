"""Start an existing environment container."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager, StateManager


class EnvStartCommand(PlumbingCommand):
  """Start an existing environment container."""

  def execute(self, args) -> dict:
    """Start environment and return status."""
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
        "error": f"Environment '{context.name}' not found",
        "code": "ENV_NOT_FOUND",
      }

    # Start the environment
    try:
      docker = DockerClient()
      container_id = env_state["container_id"]

      # Check if already running
      container_info = docker.inspect_container(container_id)
      if container_info.get("State", {}).get("Running", False):
        return {
          "name": context.name,
          "container_id": container_id,
          "state": "running",
          "message": "Environment is already running",
        }

      # Start the container
      docker.start_container(container_id)

      # Update context last_used
      from datetime import datetime

      context.last_used = datetime.utcnow().isoformat()
      context_manager.update_context(context)

      return {
        "name": context.name,
        "container_id": container_id,
        "state": "running",
      }
    except Exception as e:
      return {
        "error": str(e),
        "code": "START_FAILED",
      }
