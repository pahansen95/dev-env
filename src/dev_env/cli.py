"""Command-line interface using argparse"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .docker import DockerClient
from .config import load_environment
from .state import StateManager
from .utils import check_docker_available, generate_container_name


def cmd_up(args: argparse.Namespace) -> int:
  """Start a development environment"""
  # Check Docker availability
  if not check_docker_available():
    print("Error: Docker daemon is not accessible", file=sys.stderr)
    return 1

  # Load configuration
  try:
    env = load_environment(args.config)
  except Exception as e:
    print(f"Error loading configuration: {e}", file=sys.stderr)
    return 1

  # Initialize state manager
  state = StateManager(args.state_dir)

  # Check if environment already exists
  env_name = args.name or env.name
  if state.get_environment(env_name):
    print(f"Environment '{env_name}' already exists", file=sys.stderr)
    return 1

  # Create Docker client
  docker = DockerClient()

  try:
    # Generate container name
    container_name = generate_container_name(env_name)

    print(f"Creating environment '{env_name}'...")

    # Create volumes if specified
    volumes = {}
    if env.volumes:
      for vol in env.volumes:
        if vol.type == "named":
          print(f"  Creating volume: {vol.name}")
          docker.create_volume(vol.name, labels={"dev-env": env_name})
        volumes[vol.source] = {"bind": vol.target, "mode": vol.mode}

    # Prepare environment variables
    environment = env.environment or {}
    environment["DEV_ENV_NAME"] = env_name

    # Create container
    print(f"  Creating container: {container_name}")
    container_id = docker.create_container(
      name=container_name,
      image=env.base_image,
      command=env.command,
      environment=environment,
      volumes=volumes,
      ports=env.ports,
    )

    # Start container
    print("  Starting container...")
    docker.start_container(container_id)

    # Save state
    state.save_environment(
      env_name,
      {
        "container_id": container_id,
        "container_name": container_name,
        "config": env.to_dict(),
        "volumes": [v.name for v in env.volumes if v.type == "named"] if env.volumes else [],
      },
    )

    print(f"Environment '{env_name}' is up and running!")

    # Show connection info
    if env.ports and 22 in env.ports:
      ssh_port = env.ports[22].get("HostPort", 22) if isinstance(env.ports[22], dict) else 22
      print(f"SSH access: ssh -p {ssh_port} root@localhost")

    return 0

  except Exception as e:
    print(f"Error creating environment: {e}", file=sys.stderr)
    # Cleanup on error
    try:
      state.remove_environment(env_name)
    except:
      pass
    return 1


def cmd_down(args: argparse.Namespace) -> int:
  """Stop and remove a development environment"""
  if not check_docker_available():
    print("Error: Docker daemon is not accessible", file=sys.stderr)
    return 1

  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    print(f"Environment '{args.name}' not found", file=sys.stderr)
    return 1

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
        except:
          print(f"    Warning: Failed to remove volume {volume}")

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

  print(f"{'NAME':<20} {'STATUS':<10} {'CONTAINER':<12} {'IMAGE':<30}")
  print("-" * 72)

  for name, env_state in environments.items():
    status = "unknown"
    if docker:
      try:
        container = docker.get_container(env_state["container_id"])
        status = container["State"]["Status"]
      except:
        status = "not found"

    config = env_state.get("config", {})
    image = config.get("base_image", "unknown")[:30]
    container_id = env_state["container_id"][:12]

    print(f"{name:<20} {status:<10} {container_id:<12} {image:<30}")

  return 0


def cmd_exec(args: argparse.Namespace) -> int:
  """Execute a command in an environment"""
  print("Error: 'exec' command not yet implemented", file=sys.stderr)
  return 1


def cmd_ssh(args: argparse.Namespace) -> int:
  """SSH into an environment"""
  state = StateManager(args.state_dir)
  env_state = state.get_environment(args.name)

  if not env_state:
    print(f"Environment '{args.name}' not found", file=sys.stderr)
    return 1

  config = env_state.get("config", {})
  ports = config.get("ports", {})

  if "22" not in ports and 22 not in ports:
    print(f"Environment '{args.name}' does not have SSH enabled", file=sys.stderr)
    return 1

  ssh_port = 22
  port_config = ports.get("22") or ports.get(22)
  if isinstance(port_config, dict):
    ssh_port = port_config.get("HostPort", 22)

  # Use subprocess to exec ssh
  import subprocess

  ssh_args = ["ssh", "-p", str(ssh_port)]
  if args.ssh_args:
    ssh_args.extend(args.ssh_args)
  ssh_args.append("root@localhost")

  return subprocess.call(ssh_args)


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
  list_parser = subparsers.add_parser("list", help="List all environments")

  # exec command
  exec_parser = subparsers.add_parser("exec", help="Execute command in environment")
  exec_parser.add_argument("name", help="Environment name")
  exec_parser.add_argument("command", nargs="+", help="Command to execute")

  # ssh command
  ssh_parser = subparsers.add_parser("ssh", help="SSH into environment")
  ssh_parser.add_argument("name", help="Environment name")
  ssh_parser.add_argument("ssh_args", nargs="*", help="Additional SSH arguments")

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
  }

  return commands[args.command](args)


if __name__ == "__main__":
  sys.exit(main())
