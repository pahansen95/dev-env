"""Attach to environment container TTY."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager, StateManager


class AttachCommand(PlumbingCommand):
  """Attach to environment container's TTY."""

  def execute(self, args) -> dict:
    """Attach to container - this command is special as it takes over the TTY."""
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

    # Attach to container
    try:
      docker = DockerClient()
      container_id = env_state["container_id"]

      # Check if running
      container_info = docker.inspect_container(container_id)
      if not container_info.get("State", {}).get("Running", False):
        return {
          "error": "Environment is not running",
          "code": "ENV_NOT_RUNNING",
        }

      # Note: For attach, we need to output the container info before attaching
      # since attach will take over the TTY
      attach_info = {
        "name": context.name,
        "container_id": container_id,
        "action": "attach",
        "message": "Attaching to container. Press Ctrl-P Ctrl-Q to detach.",
      }
      self.output(attach_info)

      # This would take over the TTY - simplified for now
      import subprocess

      subprocess.run(["docker", "attach", container_id])

      # This return is only reached after detaching
      return {
        "name": context.name,
        "container_id": container_id,
        "action": "detached",
      }
    except Exception as e:
      return {
        "error": str(e),
        "code": "ATTACH_FAILED",
      }
