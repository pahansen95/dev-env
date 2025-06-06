"""Stop a running environment container."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager, StateManager


class EnvStopCommand(PlumbingCommand):
  """Stop a running environment container."""

  def execute(self, args) -> dict:
    """Stop environment and return status."""
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

    # Stop the environment
    try:
      docker = DockerClient()
      container_id = env_state["container_id"]
      cleanup_errors = []

      # Check container state
      try:
        container_info = docker.inspect_container(container_id)
        is_running = container_info.get("State", {}).get("Running", False)
      except Exception:
        # Container might not exist
        is_running = False

      # Stop the container if running
      if is_running:
        docker.stop_container(container_id)

      # Remove the container
      try:
        docker.remove_container(container_id)
      except Exception as e:
        cleanup_errors.append(f"Failed to remove container: {e}")

      # Clean up network if specified
      if "network" in env_state and env_state["network"]:
        try:
          docker.remove_network(env_state["network"])
        except Exception as e:
          # Network might be in use by other containers or already removed
          cleanup_errors.append(f"Failed to remove network: {e}")

      # Clean up volumes if specified
      if "volumes" in env_state and env_state["volumes"]:
        for volume in env_state["volumes"]:
          if isinstance(volume, str):  # Named volumes only
            try:
              docker.remove_volume(volume)
            except Exception as e:
              cleanup_errors.append(f"Failed to remove volume {volume}: {e}")

      # Remove environment state
      state_manager.remove_environment(context.name)

      # Update context state
      context.state = "inactive"
      context_manager.update_context(context)

      result = {
        "name": context.name,
        "container_id": container_id,
        "state": "stopped",
        "resources_cleaned": True,
      }

      if cleanup_errors:
        result["cleanup_warnings"] = cleanup_errors

      return result

    except Exception as e:
      return {
        "error": str(e),
        "code": "STOP_FAILED",
      }
