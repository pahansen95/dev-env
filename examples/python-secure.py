"""Secure Python development environment with security hardening"""

from dev_env.config import Environment, VolumeMount, SSHConfig, SecurityConfig, ResourceConfig

# Secure Python environment with hardened configuration
environment = Environment(
  name="python-secure",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  # Environment variables
  environment={
    "PYTHONUNBUFFERED": "1",
    "PIP_NO_CACHE_DIR": "1",
  },
  # Volume mounts - only safe directories
  volumes=[
    VolumeMount(source="./src", target="/workspace", mode="rw"),
    VolumeMount(source="python-secure-cache", target="/home/dev/.cache", type="named"),
  ],
  # Port mappings - localhost only binding
  ports={
    22: {"HostPort": 2223, "HostIp": "127.0.0.1"},  # SSH access (localhost only)
    8000: {"HostPort": 8001, "HostIp": "127.0.0.1"},  # Development server (localhost only)
  },
  # SSH configuration
  ssh=SSHConfig(port=22, password_auth=False),
  # Security configuration - run as non-root user
  security=SecurityConfig(
    user="1000:1000",  # Non-root user
    drop_capabilities=["ALL"],  # Drop all capabilities
    add_capabilities=["CHOWN"],  # Only add necessary capabilities
    no_new_privileges=True,  # Prevent privilege escalation
    read_only_root_fs=False,  # Allow writes to non-root filesystem
  ),
  # Resource constraints
  resources=ResourceConfig(
    memory="1g",  # Limit memory usage
    cpus=1.0,  # Limit CPU usage
    pids_limit=500,  # Limit number of processes
  ),
)
