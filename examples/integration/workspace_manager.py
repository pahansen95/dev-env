#!/usr/bin/env python3
"""
Direct API Integration Example

This demonstrates integrating dev-env into another project by directly
using the core API rather than subprocess calls. This approach provides:
- Better error handling and control flow
- Direct access to container state and operations
- Programmatic environment management
- Integration into existing Python applications
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add dev_env to Python path for import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import core dev-env components
from dev_env.docker import DockerClient
from dev_env.state import StateManager
from dev_env.config import Environment, VolumeMount, GitConfig, SSHConfig
from dev_env.utils import (
  check_docker_available,
  generate_container_name,
  setup_ssh_server,
  inject_ssh_key,
  get_host_ssh_key,
  setup_git_in_container,
  apply_security_defaults,
  validate_port_mappings,
  validate_bind_mounts,
)


class DevEnvironmentManager:
  """High-level API for managing development environments programmatically"""

  def __init__(self, state_dir: Optional[Path] = None):
    self.state_dir = state_dir or Path.home() / ".dev-env" / "api-state"
    self.state_dir.mkdir(parents=True, exist_ok=True)
    self.state = StateManager(self.state_dir)
    self.docker = None

  def _ensure_docker(self):
    """Ensure Docker client is initialized and available"""
    if not check_docker_available():
      raise RuntimeError("Docker is not available")
    if not self.docker:
      self.docker = DockerClient()

  def create_environment(
    self,
    name: str,
    base_image: str,
    volumes: Optional[Dict[str, str]] = None,
    ports: Optional[Dict[int, int]] = None,
    git_url: Optional[str] = None,
    environment_vars: Optional[Dict[str, str]] = None,
    enable_ssh: bool = True,
    memory: str = "2g",
    cpus: float = 2.0,
  ) -> Dict[str, Any]:
    """
    Create a new development environment with simplified parameters.

    Returns dict with:
    - container_id: Docker container ID
    - container_name: Generated container name
    - ssh_port: SSH port if enabled
    - status: Current status
    """
    self._ensure_docker()

    # Check if environment already exists
    if self.state.get_environment(name):
      raise ValueError(f"Environment '{name}' already exists")

    # Build volume mounts
    volume_mounts = []
    if volumes:
      for source, target in volumes.items():
        volume_mounts.append(VolumeMount(source=source, target=target))

    # Build port configuration
    port_config = {}
    if enable_ssh:
      ssh_port = self._find_free_port(2222)
      port_config[22] = {"HostPort": ssh_port}
    if ports:
      for container_port, host_port in ports.items():
        port_config[container_port] = {"HostPort": host_port}

    # Create environment configuration
    env_config = Environment(
      name=name,
      base_image=base_image,
      command=["/bin/bash"],
      volumes=volume_mounts,
      ports=port_config,
      environment=environment_vars or {},
      ssh=SSHConfig(port=22) if enable_ssh else None,
      memory=memory,
      cpus=cpus,
    )

    # Add Git configuration if provided
    if git_url:
      env_config.git = GitConfig(url=git_url, path="/workspace")

    # Apply security defaults and validate
    apply_security_defaults(env_config)

    # Validate configuration
    warnings = []
    if env_config.ports:
      warnings.extend(validate_port_mappings(env_config.ports))
    if env_config.volumes:
      warnings.extend(validate_bind_mounts(env_config.volumes))

    # Create container
    container_name = generate_container_name(name)

    print(f"Creating environment '{name}'...")

    # Pull image if needed
    print(f"Pulling image: {base_image}")
    try:
      self.docker.pull_image(base_image)
    except Exception as e:
      # Check if image exists locally
      try:
        self.docker._request("GET", f"/images/{base_image}/json")
        print(f"Using local image: {base_image}")
      except:
        raise RuntimeError(f"Failed to pull image: {e}")

    # Create volumes
    docker_volumes = {}
    for vol in volume_mounts:
      if vol.is_named_volume():
        print(f"Creating volume: {vol.name}")
        self.docker.create_volume(vol.name, labels={"dev-env": name})
      docker_volumes[vol.source] = {"bind": vol.target, "mode": vol.mode}

    # Create container
    print(f"Creating container: {container_name}")
    container_id = self.docker.create_container(
      name=container_name,
      image=base_image,
      command=env_config.command,
      environment=env_config.environment,
      volumes=docker_volumes,
      ports=env_config.ports,
      env_config=env_config,
    )

    # Start container
    print("Starting container...")
    self.docker.start_container(container_id)

    # Setup SSH if enabled
    ssh_port = None
    if enable_ssh:
      print("Setting up SSH...")
      try:
        setup_ssh_server(self.docker, container_id)
        public_key = get_host_ssh_key()
        inject_ssh_key(self.docker, container_id, public_key)
        self.docker.exec_run(container_id, ["/usr/sbin/sshd"], user="root")
        ssh_port = port_config[22]["HostPort"]
        print(f"SSH enabled on port {ssh_port}")
      except Exception as e:
        print(f"Warning: SSH setup failed: {e}")

    # Setup Git if configured
    if git_url:
      print(f"Cloning repository: {git_url}")
      try:
        from dev_env.utils import get_host_git_config

        host_git_config = get_host_git_config()
        setup_git_in_container(self.docker, container_id, env_config.git, host_git_config)
      except Exception as e:
        print(f"Warning: Git setup failed: {e}")

    # Wait for container to be ready
    if self.docker.wait_for_container_ready(container_id, timeout=30):
      print("✅ Container is ready!")
    else:
      print("⚠️  Container readiness check timed out")

    # Save state
    state_data = {
      "container_id": container_id,
      "container_name": container_name,
      "config": env_config.__dict__,
      "volumes": [v.name for v in volume_mounts if v.is_named_volume()],
      "network": None,
    }
    self.state.save_environment(name, state_data)

    return {
      "container_id": container_id,
      "container_name": container_name,
      "ssh_port": ssh_port,
      "ports": port_config,
      "status": "running",
      "warnings": warnings,
    }

  def execute_command(self, name: str, command: list[str], user: str = "root") -> tuple[str, int]:
    """Execute a command in an environment and return output"""
    self._ensure_docker()

    env_state = self.state.get_environment(name)
    if not env_state:
      raise ValueError(f"Environment '{name}' not found")

    container_id = env_state["container_id"]

    # Check if container is running
    container = self.docker.get_container(container_id)
    if container["State"]["Status"] != "running":
      raise RuntimeError(f"Environment '{name}' is not running")

    # Execute command
    output, exit_code = self.docker.exec_run(container_id=container_id, cmd=command, user=user)

    return output.decode("utf-8", errors="replace"), exit_code

  def stop_environment(self, name: str, remove_volumes: bool = False) -> bool:
    """Stop and remove an environment"""
    self._ensure_docker()

    env_state = self.state.get_environment(name)
    if not env_state:
      raise ValueError(f"Environment '{name}' not found")

    container_id = env_state["container_id"]

    print(f"Stopping environment '{name}'...")

    # Stop and remove container
    try:
      self.docker.stop_container(container_id)
      self.docker.remove_container(container_id)
    except Exception as e:
      print(f"Warning: Container removal failed: {e}")

    # Remove volumes if requested
    if remove_volumes and env_state.get("volumes"):
      for volume in env_state["volumes"]:
        try:
          self.docker.remove_volume(volume)
          print(f"Removed volume: {volume}")
        except Exception as e:
          print(f"Warning: Failed to remove volume {volume}: {e}")

    # Remove state
    self.state.remove_environment(name)

    print(f"✅ Environment '{name}' removed")
    return True

  def get_environment_info(self, name: str) -> Optional[Dict[str, Any]]:
    """Get detailed information about an environment"""
    self._ensure_docker()

    env_state = self.state.get_environment(name)
    if not env_state:
      return None

    # Get container status
    try:
      container = self.docker.get_container(env_state["container_id"])
      status = container["State"]["Status"]
    except:
      status = "not found"

    return {
      "name": name,
      "container_id": env_state["container_id"],
      "container_name": env_state["container_name"],
      "status": status,
      "config": env_state.get("config", {}),
      "volumes": env_state.get("volumes", []),
      "created_at": env_state.get("created_at"),
      "updated_at": env_state.get("updated_at"),
    }

  def list_environments(self) -> Dict[str, Dict[str, Any]]:
    """List all environments with their status"""
    self._ensure_docker()
    return self.state.list_environments()

  def _find_free_port(self, start_port: int) -> int:
    """Find a free port starting from start_port"""
    import socket

    port = start_port
    while port < 65535:
      try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
          s.bind(("127.0.0.1", port))
          return port
      except OSError:
        port += 1
    raise RuntimeError("No free ports available")


# Example usage
def demo_api_usage():
  """Demonstrate direct API usage"""

  manager = DevEnvironmentManager()

  # Create a Python development environment
  env_info = manager.create_environment(
    name="api-demo",
    base_image="python:3.13-slim",
    volumes={".": "/workspace", "pip-cache": "/root/.cache/pip"},
    ports={8000: 8000},
    environment_vars={"PYTHONUNBUFFERED": "1", "ENVIRONMENT": "development"},
    enable_ssh=True,
    memory="2g",
    cpus=2.0,
  )

  print("\nEnvironment created:")
  print(f"  Container ID: {env_info['container_id']}")
  print(f"  SSH Port: {env_info['ssh_port']}")
  print(f"  Ports: {env_info['ports']}")

  # Execute commands
  print("\nInstalling packages...")
  output, exit_code = manager.execute_command("api-demo", ["pip", "install", "fastapi", "uvicorn"])

  if exit_code == 0:
    print("✅ Packages installed successfully")

  # Create a simple FastAPI app
  app_code = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World", "Environment": "api-demo"}
"""

  output, exit_code = manager.execute_command("api-demo", ["sh", "-c", f"echo '{app_code}' > /workspace/main.py"])

  # Get environment info
  info = manager.get_environment_info("api-demo")
  print(f"\nEnvironment status: {info['status']}")

  # List all environments
  all_envs = manager.list_environments()
  print(f"\nTotal environments: {len(all_envs)}")

  # Cleanup (uncomment to run)
  # manager.stop_environment("api-demo", remove_volumes=True)

  return manager


if __name__ == "__main__":
  demo_api_usage()
