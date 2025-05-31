#!/usr/bin/env python3
"""
Security-Hardened Python Development Environment

This example demonstrates security best practices:
- Non-root user execution (uid 1000)
- Dropped capabilities
- Resource limits
- No privileged operations
- Read-only root filesystem

Usage:
  python -m dev_env up examples/python-secure.py

Note: The non-root user and read-only filesystem require
careful volume mount configuration for writable areas.
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, SSHConfig, SecurityLevel

# Get current directory
current_dir = Path.cwd()

# Security-focused Python environment
config = Environment(
  name="python-secure",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  # Security configuration
  user="1000:1000",  # Non-root user
  drop_capabilities=["ALL"],  # Drop all capabilities
  add_capabilities=[],  # Add only what's needed
  no_new_privileges=True,  # Prevent privilege escalation
  read_only_root_fs=True,  # Read-only root filesystem
  security_level=SecurityLevel.STANDARD,
  volumes=[
    # Mount workspace as read-write (specific exception)
    VolumeMount(source=str(current_dir), target="/workspace"),
    # Temporary directories for Python
    VolumeMount(source="python-tmp", target="/tmp"),
    # Home directory for user files
    VolumeMount(source="python-home", target="/home/developer"),
    # Python needs writable areas for packages
    VolumeMount(source="python-local", target="/home/developer/.local"),
  ],
  # SSH access (will run as non-root user)
  ports={22: {"HostPort": 2223}},
  ssh=SSHConfig(port=22),
  # Security-conscious environment variables
  environment={
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_NO_CACHE_DIR": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "HOME": "/home/developer",
    "USER": "developer",
    "PATH": "/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin",
  },
  # Resource limits
  memory="2g",
  cpus=2.0,
  pids_limit=500,  # Limit process creation
)

# Note: Due to security constraints, package installation must be done
# in user space after container creation:
# pip install --user ipython pytest black flake8 mypy
