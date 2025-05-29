"""Python development environment with Git repository"""

from dev_env.config import Environment, VolumeMount, GitConfig

# Define the development environment
environment = Environment(
  name="python-dev",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  # Environment variables
  environment={
    "PYTHONPATH": "/workspace",
    "DEBIAN_FRONTEND": "noninteractive",
  },
  # Port mappings (SSH enabled)
  ports={
    22: {"HostPort": 2222},  # SSH access
    8000: {"HostPort": 8000},  # Development server
  },
  # Volume mounts
  volumes=[
    VolumeMount(
      source="python-dev-cache",
      target="/root/.cache",
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
)
