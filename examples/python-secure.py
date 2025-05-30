#!/usr/bin/env python3
"""
Security-Hardened Python Development Environment

This example demonstrates security best practices:
- Non-root user execution
- Read-only root filesystem
- Minimal attack surface
- Resource limits
- No privileged operations
- Isolated networking

Usage:
  dev-env run examples/python-secure.py
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount

# Get current directory
current_dir = Path.cwd()

# Security-focused Python environment
environment = Environment(
  name="python-secure",
  base_image="python:3.12-slim",
  # Run as non-root user
  user="1000:1000",
  # Read-only root filesystem
  read_only=True,
  # Drop all capabilities
  drop_capabilities=["ALL"],
  # No privileged mode
  privileged=False,
  volumes=[
    # Mount workspace as read-write (specific exception)
    VolumeMount(source=str(current_dir), target="/workspace", mode="rw"),
    # Temporary directories for Python
    VolumeMount(source="python-tmp", target="/tmp", mode="rw"),
    # Home directory for user files
    VolumeMount(source="python-home", target="/home/developer", mode="rw"),
  ],
  working_dir="/workspace",
  command=["/bin/bash"],
  # Security-conscious environment variables
  environment={
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_NO_CACHE_DIR": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "HOME": "/home/developer",
    "USER": "developer",
  },
  # Resource limits
  memory_limit="2g",
  cpu_limit="2.0",
  # Minimal init commands (run as root before dropping privileges)
  init_commands=[
    # Create non-root user
    "useradd -m -u 1000 -s /bin/bash developer",
    # Install minimal requirements
    "apt-get update && apt-get install -y --no-install-recommends git",
    # Set up Python environment for user
    "mkdir -p /home/developer/.local/bin",
    "chown -R developer:developer /home/developer",
    # Install pip packages as user
    "su - developer -c 'pip install --user --no-cache-dir ipython pytest black flake8 mypy'",
    # Clean up apt cache to reduce image size
    "apt-get clean && rm -rf /var/lib/apt/lists/*",
  ],
)
