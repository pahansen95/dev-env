"""Execute a command in the environment."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager, StateManager


class ExecCommand(PlumbingCommand):
  """Execute a command in the environment container."""

  def execute(self, args) -> dict:
    """Execute command and return results."""
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

    # Execute command
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

      # Get command from args
      command = getattr(args, "command", [])
      if not command:
        return {
          "error": "No command specified",
          "code": "NO_COMMAND",
        }

      # Execute the command
      result = docker.exec_in_container(container_id, command)

      return {
        "name": context.name,
        "command": command,
        "exit_code": result.get("exit_code", 0),
        "output": result.get("output", ""),
      }
    except Exception as e:
      return {
        "error": str(e),
        "code": "EXEC_FAILED",
      }
