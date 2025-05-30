"""Python development environment with Git repository"""

from dev_env.config import Environment, VolumeMount, GitConfig, SecurityLevel, ResourceConfig

# Define the development environment with security
environment = Environment(
  name="python-dev",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  # Environment variables
  environment={
    "PYTHONPATH": "/workspace",
    "DEBIAN_FRONTEND": "noninteractive",
  },
  # Port mappings - localhost binding for security
  ports={
    22: {"HostPort": 2222, "HostIp": "127.0.0.1"},  # SSH access (secure)
    8000: {"HostPort": 8000, "HostIp": "127.0.0.1"},  # Development server (secure)
  },
  # Volume mounts
  volumes=[
    VolumeMount(
      source="python-dev-cache",
      target="/home/dev/.cache",  # Updated for non-root user
      type="named",
    ),
  ],
  # Git repository configuration
  git=GitConfig(
    url="https://github.com/python/cpython.git",
    branch="main",
    path="/workspace",
    shallow=True,
  ),
  # Apply standard security level
  security_level=SecurityLevel.STANDARD,
  # Resource constraints for stability
  resources=ResourceConfig(
    memory="3g",  # Sufficient for CPython compilation
    cpus=2.0,  # Good for parallel builds
    pids_limit=1500,  # Handle compilation processes
  ),
)
