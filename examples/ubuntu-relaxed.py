"""Ubuntu development environment with relaxed security for compatibility"""

from dev_env.config import Environment, VolumeMount, SSHConfig, SecurityLevel, ResourceConfig

# Ubuntu environment with relaxed security for legacy applications
environment = Environment(
  name="ubuntu-legacy",
  base_image="ubuntu:22.04",
  command=["/bin/bash"],
  # Environment variables
  environment={
    "DEBIAN_FRONTEND": "noninteractive",
    "TERM": "xterm-256color",
  },
  # Volume mounts
  volumes=[
    VolumeMount(source=".", target="/workspace", mode="rw"),
    VolumeMount(source="ubuntu-home", target="/root", type="named"),
  ],
  # Port mappings - allow external access with explicit configuration
  ports={
    22: {"HostPort": 2224, "HostIp": "127.0.0.1"},  # SSH (localhost only)
    80: {"HostPort": 8080, "HostIp": "192.168.1.100"},  # Web server (specific interface)
    3000: {"HostPort": 3000, "HostIp": "127.0.0.1"},  # Development server
  },
  # SSH configuration
  ssh=SSHConfig(port=22, password_auth=False),
  # Use relaxed security preset for compatibility
  security_level=SecurityLevel.RELAXED,
  # Still apply resource constraints for stability
  resources=ResourceConfig(
    memory="4g",  # Higher memory limit for legacy apps
    cpus=2.0,  # More CPU for compilation
    pids_limit=2000,  # Higher process limit
  ),
)
