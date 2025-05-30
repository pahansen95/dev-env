"""Command-line interface using argparse"""

import argparse
import sys
import subprocess
from pathlib import Path

from . import __version__
from .docker import DockerClient
from .config import load_environment
from .state import StateManager
from .utils import (
  check_docker_available,
  generate_container_name,
  validate_port_mappings,
  validate_bind_mounts,
  apply_security_defaults,
  DevEnvError,
  ConfigError,
  DockerError,
)


def cmd_up(args: argparse.Namespace) -> int:
  """Start a development environment"""
  # Check Docker availability
  if not check_docker_available():
    error = DockerError.daemon_unavailable()
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  # Load configuration
  try:
    env = load_environment(args.config)
    # Apply security defaults and validate
    apply_security_defaults(env)
  except ConfigError as e:
    print(e.format_error(), file=sys.stderr)
    return e.exit_code
  except Exception as e:
    print(f"Error loading configuration: {e}", file=sys.stderr)
    return 1

  # Initialize state manager
  state = StateManager(args.state_dir)

  # Check if environment already exists
  env_name = args.name or env.name
  if state.get_environment(env_name):
    error = ConfigError.environment_exists(env_name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  # Validate configuration before proceeding
  warnings = []

  # Validate port mappings
  if env.ports:
    port_warnings = validate_port_mappings(env.ports)
    warnings.extend(port_warnings)

  # Validate bind mounts
  if env.volumes:
    mount_warnings = validate_bind_mounts(env.volumes)
    warnings.extend(mount_warnings)

  # Show warnings to user
  if warnings:
    print("⚠️  Configuration warnings:")
    for warning in warnings:
      print(f"  - {warning}")

    # Ask user if they want to continue
    response = input("\nContinue anyway? [y/N]: ").strip().lower()
    if response not in ["y", "yes"]:
      print("Aborted by user")
      return 1

  # Create Docker client
  docker = DockerClient()

  try:
    # Generate container name
    container_name = generate_container_name(env_name)

    print(f"Creating environment '{env_name}'...")

    # Pull image if needed
    def progress_callback(status: str, progress: float):
      print(f"    {status}: {progress:.1f}%")

    print(f"  [1/6] Pulling image: {env.base_image}")
    try:
      docker.pull_image(env.base_image, progress_callback)
    except Exception as e:
      # Check if image exists locally before failing
      try:
        docker._request("GET", f"/images/{env.base_image}/json")
        print(f"    Warning: Pull failed, using local image: {e}")
      except RuntimeError:
        # Image doesn't exist locally either
        error = DockerError.image_pull_failed(env.base_image, str(e))
        print(error.format_error(), file=sys.stderr)
        return error.exit_code

    # Create volumes if specified
    volumes = {}
    if env.volumes:
      print("  [2/6] Creating volumes...")
      for vol in env.volumes:
        if vol.is_named_volume():
          print(f"    Creating volume: {vol.name}")
          docker.create_volume(vol.name, labels={"dev-env": env_name})
        volumes[vol.source] = {"bind": vol.target, "mode": vol.mode}
    else:
      print("  [2/6] No volumes to create")

    # Create custom network if specified
    network_name = None
    if env.network and env.network.name:
      print(f"  [2.5/6] Creating custom network: {env.network.name}")
      try:
        # Attempt to create network (will succeed if it doesn't exist)
        docker.create_network(
          name=env.network.name, driver=env.network.driver, options=env.network.options, labels=env.network.labels
        )
        print(f"    Created network: {env.network.name}")
      except RuntimeError as e:
        # Network likely already exists, which is fine
        if "already exists" in str(e):
          print(f"    Network already exists: {env.network.name}")
        else:
          raise
      network_name = env.network.name

    # Prepare environment variables
    environment = env.environment or {}
    environment["DEV_ENV_NAME"] = env_name

    # Create container
    print(f"  [3/6] Creating container: {container_name}")
    container_id = docker.create_container(
      name=container_name,
      image=env.base_image,
      command=env.command,
      environment=environment,
      volumes=volumes,
      ports=env.ports,
      network=network_name,
      env_config=env,
    )

    # Start container
    print("  [4/6] Starting container...")
    docker.start_container(container_id)

    # Setup SSH if port 22 is exposed
    ssh_enabled = env.ports and (22 in env.ports or "22" in env.ports)
    if ssh_enabled:
      print("  [5/6] Setting up SSH server...")
      try:
        from .utils import setup_ssh_server, inject_ssh_key, get_host_ssh_key

        # Setup SSH server with progress
        print("    Installing SSH server...")
        setup_ssh_server(docker, container_id)

        # Get and inject host SSH key
        print("    Configuring SSH keys...")
        public_key = get_host_ssh_key()
        inject_ssh_key(docker, container_id, public_key)

        # Start SSH daemon in background
        print("    Starting SSH daemon...")
        docker.exec_run(container_id, ["/usr/sbin/sshd"], user="root")

        print("    SSH server configured and started")
      except Exception as e:
        print(f"    Warning: SSH setup failed: {e}")
    else:
      print("  [5/6] SSH not enabled")

    # Setup Git repository if configured
    if env.git:
      print("  [6/6] Setting up Git repository...")
      try:
        from .utils import setup_git_in_container, get_host_git_config

        # Get host git configuration
        print("    Installing Git and configuring...")
        host_git_config = get_host_git_config()

        # Setup git and clone repository
        print(f"    Cloning repository: {env.git.url}")
        setup_git_in_container(docker, container_id, env.git, host_git_config)

        print(f"    Repository cloned to {env.git.path}")
      except Exception as e:
        print(f"    Warning: Git setup failed: {e}")
    else:
      print("  [6/6] No Git repository configured")

    # Wait for container to be ready
    print("\n  Final checks: Waiting for container to be ready...")
    import time

    start_time = time.time()
    if docker.wait_for_container_ready(container_id, timeout=30):
      elapsed = time.time() - start_time
      print(f"  ✅ Container is ready! (took {elapsed:.1f}s)")
    else:
      print("  ⚠️  Warning: Container readiness check timed out")

    # Save state
    state.save_environment(
      env_name,
      {
        "container_id": container_id,
        "container_name": container_name,
        "config": env.__dict__,
        "volumes": [v.name for v in env.volumes if v.is_named_volume()] if env.volumes else [],
        "network": network_name if network_name else None,
      },
    )

    print(f"Environment '{env_name}' is up and running!")

    # Show connection info
    if ssh_enabled:
      ssh_port = env.ports[22].get("HostPort", 22) if isinstance(env.ports[22], dict) else 22
      print(f"SSH access: ssh -p {ssh_port} root@localhost")

    return 0

  except DevEnvError as e:
    print(e.format_error(), file=sys.stderr)
    # Cleanup on error
    try:
      state.remove_environment(env_name)
    except Exception:
      pass
    return e.exit_code
  except Exception as e:
    print(f"Unexpected error creating environment: {e}", file=sys.stderr)
    # Cleanup on error
    try:
      state.remove_environment(env_name)
    except Exception:
      pass
    return 1


def cmd_down(args: argparse.Namespace) -> int:
  """Stop and remove a development environment"""
  if not check_docker_available():
    error = DockerError.daemon_unavailable()
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    error = ConfigError.environment_not_found(args.name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  docker = DockerClient()

  try:
    print(f"Stopping environment '{args.name}'...")

    # Stop and remove container
    container_id = env_state["container_id"]
    print("  Stopping container...")
    docker.stop_container(container_id)
    print("  Removing container...")
    docker.remove_container(container_id)

    # Remove volumes if requested
    if args.volumes and env_state.get("volumes"):
      for volume in env_state["volumes"]:
        print(f"  Removing volume: {volume}")
        try:
          docker.remove_volume(volume)
        except Exception:
          print(f"    Warning: Failed to remove volume {volume}")

    # Remove custom network if it exists
    if env_state.get("network"):
      network_name = env_state["network"]
      print(f"  Removing network: {network_name}")
      try:
        docker.remove_network(network_name)
        print(f"    Removed network: {network_name}")
      except Exception as e:
        if "has active endpoints" in str(e):
          print(f"    Network {network_name} has other containers, keeping it")
        else:
          print(f"    Warning: Could not remove network {network_name}: {e}")

    # Remove state
    state.remove_environment(args.name)

    print(f"Environment '{args.name}' has been removed")
    return 0

  except Exception as e:
    print(f"Error removing environment: {e}", file=sys.stderr)
    return 1


def cmd_list(args: argparse.Namespace) -> int:
  """List all development environments"""
  state = StateManager(args.state_dir)
  environments = state.list_environments()

  if not environments:
    print("No environments found")
    return 0

  docker = DockerClient() if check_docker_available() else None

  print(f"{'NAME':<20} {'STATUS':<10} {'CONTAINER':<12} {'IMAGE':<25} {'VOLUMES':<15}")
  print("-" * 87)

  for name, env_state in environments.items():
    status = "unknown"
    if docker:
      try:
        container = docker.get_container(env_state["container_id"])
        status = container["State"]["Status"]
      except Exception:
        status = "not found"

    config = env_state.get("config", {})
    image = config.get("base_image", "unknown")[:25]
    container_id = env_state["container_id"][:12]

    # Get volume info
    volumes_info = "none"
    if env_state.get("volumes") and docker:
      volume_count = len(env_state["volumes"])
      volumes_info = f"{volume_count} vols" if volume_count > 0 else "0 vols"

    print(f"{name:<20} {status:<10} {container_id:<12} {image:<25} {volumes_info:<15}")

  return 0


def cmd_exec(args: argparse.Namespace) -> int:
  """Execute a command in an environment"""
  if not check_docker_available():
    error = DockerError.daemon_unavailable()
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    error = ConfigError.environment_not_found(args.name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  docker = DockerClient()

  try:
    container_id = env_state["container_id"]

    # Check if container is running
    container = docker.get_container(container_id)
    if container["State"]["Status"] != "running":
      error = DockerError.container_not_running(args.name)
      print(error.format_error(), file=sys.stderr)
      return error.exit_code

    # Execute command and get result
    output, exit_code = docker.exec_run(
      container_id=container_id,
      cmd=args.command,
    )

    # Print output
    if output:
      print(output.decode("utf-8", errors="replace"), end="")

    return exit_code

  except Exception as e:
    print(f"Error executing command: {e}", file=sys.stderr)
    return 1


def cmd_ssh(args: argparse.Namespace) -> int:
  """SSH into an environment"""
  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    error = ConfigError.environment_not_found(args.name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  config = env_state.get("config", {})
  ports = config.get("ports", {})

  if "22" not in ports and 22 not in ports:
    error = ConfigError.ssh_not_enabled(args.name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  ssh_port = 22
  port_config = ports.get("22") or ports.get(22)
  if isinstance(port_config, dict):
    ssh_port = port_config.get("HostPort", 22)

  # Use subprocess to exec ssh

  ssh_args = ["ssh", "-p", str(ssh_port)]
  if args.ssh_args:
    ssh_args.extend(args.ssh_args)
  ssh_args.append("root@localhost")

  return subprocess.call(ssh_args)


def cmd_logs(args: argparse.Namespace) -> int:
  """Show container logs"""
  if not check_docker_available():
    error = DockerError.daemon_unavailable()
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    error = ConfigError.environment_not_found(args.name)
    print(error.format_error(), file=sys.stderr)
    return error.exit_code

  docker = DockerClient()

  try:
    container_id = env_state["container_id"]

    # Get logs
    logs = docker.get_container_logs(container_id=container_id, follow=args.follow, tail=args.tail)

    # Print logs, handling Docker's log format
    if logs:
      # Docker logs can contain header bytes, we need to handle this
      output = logs.decode("utf-8", errors="replace")
      print(output, end="")

    return 0

  except Exception as e:
    print(f"Error getting logs: {e}", file=sys.stderr)
    return 1


def main():
  """Main CLI entry point"""
  parser = argparse.ArgumentParser(prog="dev-env", description="Zero-dependency development environment management")
  parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
  parser.add_argument(
    "--state-dir", type=Path, default=Path.home() / ".dev-env" / "state", help="Directory for storing environment state"
  )

  subparsers = parser.add_subparsers(dest="command", help="Available commands")

  # up command
  up_parser = subparsers.add_parser("up", help="Create and start an environment")
  up_parser.add_argument("config", type=Path, help="Path to environment configuration")
  up_parser.add_argument("--name", help="Override environment name")

  # down command
  down_parser = subparsers.add_parser("down", help="Stop and remove an environment")
  down_parser.add_argument("name", help="Environment name")
  down_parser.add_argument("--volumes", action="store_true", help="Also remove volumes")

  # list command
  subparsers.add_parser("list", help="List all environments")

  # exec command
  exec_parser = subparsers.add_parser("exec", help="Execute command in environment")
  exec_parser.add_argument("name", help="Environment name")
  exec_parser.add_argument("command", nargs="+", help="Command to execute")

  # ssh command
  ssh_parser = subparsers.add_parser("ssh", help="SSH into environment")
  ssh_parser.add_argument("name", help="Environment name")
  ssh_parser.add_argument("ssh_args", nargs="*", help="Additional SSH arguments")

  # logs command
  logs_parser = subparsers.add_parser("logs", help="Show container logs")
  logs_parser.add_argument("name", help="Environment name")
  logs_parser.add_argument("-f", "--follow", action="store_true", help="Follow log output")
  logs_parser.add_argument("--tail", type=int, help="Number of lines to show from end of logs")

  # completion command
  from .completion import add_completion_parser

  add_completion_parser(subparsers)

  args = parser.parse_args()

  if not args.command:
    parser.print_help()
    return 1

  # Ensure state directory exists
  args.state_dir.mkdir(parents=True, exist_ok=True)

  # Dispatch to command handler
  commands = {
    "up": cmd_up,
    "down": cmd_down,
    "list": cmd_list,
    "exec": cmd_exec,
    "ssh": cmd_ssh,
    "logs": cmd_logs,
  }

  try:
    # Handle completion command specially since it uses a different pattern
    if hasattr(args, "func"):
      return args.func(args)

    return commands[args.command](args)
  except DevEnvError as e:
    print(e.format_error(), file=sys.stderr)
    return e.exit_code


if __name__ == "__main__":
  sys.exit(main())
