#!/usr/bin/env python3
"""
Basic Python Development Environment

This example demonstrates a simple Python development environment with:
- Python 3.13 runtime
- Project code mounted at /workspace
- SSH access for remote development
- Persistent pip cache

Usage:
  python -m dev_env up examples/python.py

After starting:
  python -m dev_env ssh python-dev
  # Install development tools manually:
  # pip install ipython pytest black flake8 mypy
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, SSHConfig

# Get the current directory for mounting
current_dir = Path.cwd()

# Define the environment configuration
config = Environment(
  name="python-dev",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  volumes=[
    # Mount current directory as workspace
    VolumeMount(source=str(current_dir), target="/workspace"),
    # Persist pip cache
    VolumeMount(source="pip-cache", target="/root/.cache/pip"),
  ],
  # Enable SSH access
  ports={22: {"HostPort": 2222}},
  # Common environment variables for Python development
  environment={
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_NO_CACHE_DIR": "0",  # Allow caching since we have persistent volume
  },
  # SSH configuration
  ssh=SSHConfig(port=22),
  # Resource allocation
  memory="2g",
  cpus=2.0,
)
