#!/usr/bin/env python3
"""
Basic Python Development Environment

This example demonstrates a simple Python development environment with:
- Python 3.12 runtime
- Project code mounted at /workspace
- Common Python development tools pre-installed
- Interactive shell with working directory set

Usage:
  dev-env run examples/python.py
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount

# Get the current directory for mounting
current_dir = Path.cwd()

# Define the environment configuration
environment = Environment(
  name="python-dev",
  base_image="python:3.12-slim",
  volumes=[
    # Mount current directory as workspace
    VolumeMount(source=str(current_dir), target="/workspace", mode="rw")
  ],
  # Set working directory to the mounted workspace
  working_dir="/workspace",
  # Run bash shell for interactive development
  command=["/bin/bash"],
  # Common environment variables for Python development
  environment={"PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1", "PIP_NO_CACHE_DIR": "1"},
  # Install common development tools on startup
  init_commands=[
    "apt-get update && apt-get install -y git curl vim",
    "pip install --upgrade pip setuptools wheel",
    "pip install ipython pytest black flake8 mypy",
  ],
)

# The environment will be automatically loaded by dev-env
