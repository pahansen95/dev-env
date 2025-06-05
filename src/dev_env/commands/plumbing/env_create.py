"""Create a new environment container."""

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.config import load_environment
from dev_env.context_resolver import ContextResolver
from dev_env.docker import DockerClient
from dev_env.state import ContextManager


class EnvCreateCommand(PlumbingCommand):
  """Create a new environment container from configuration."""

  def execute(self, args) -> dict:
    """Create environment and return container details."""
    # Resolve context
    manager = ContextManager()
    resolver = ContextResolver(manager)
    context_name = getattr(args, "context", None)
    context = resolver.resolve(context_name)

    if not context:
      return {
        "error": "Context not found",
        "code": "CONTEXT_NOT_FOUND",
      }

    # Load configuration
    config_path = context.path / "dev-env.yaml"
    if not config_path.exists():
      return {
        "error": f"Configuration not found at {config_path}",
        "code": "CONFIG_NOT_FOUND",
      }

    try:
      config = load_environment(config_path)
    except Exception as e:
      return {
        "error": f"Invalid configuration: {e}",
        "code": "CONFIG_INVALID",
      }

    # Create environment
    docker = DockerClient()

    try:
      # Generate container name
      from dev_env.utils import generate_container_name

      container_name = generate_container_name(context.name)

      # Check if already exists
      try:
        existing = docker.inspect_container(container_name)
        if existing:
          return {
            "error": f"Environment '{context.name}' already exists",
            "code": "ENV_EXISTS",
          }
      except Exception:
        # Container doesn't exist, which is what we want
        pass

      # Create the container

      result = docker.create_container(
        image=config.base_image,
        name=container_name,
        hostname=context.name,
        working_dir="/workspace",
        labels={
          "dev-env.name": context.name,
          "dev-env.context": context.id,
        },
      )

      # Save state
      from dev_env.state import StateManager

      state_manager = StateManager()
      state_manager.save_environment(
        context.name,
        {
          "container_id": result["Id"],
          "container_name": container_name,
          "config": config.__dict__,
        },
      )

      return {
        "name": context.name,
        "container_id": result["Id"],
        "container_name": container_name,
        "state": "created",
        "context_id": context.id,
      }
    except Exception as e:
      return {
        "error": str(e),
        "code": "CREATE_FAILED",
      }
