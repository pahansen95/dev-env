#!/usr/bin/env python3
"""
Python Development Environment with Git Integration

This example shows how to work with a Git repository:
- Clones a repository on environment startup
- SSH access for development
- Git configuration from host
- Persistent pip cache

Usage:
  python -m dev_env up examples/python-with-git.py

The repository will be cloned automatically when the
environment is created.
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, GitConfig, SSHConfig

# Configure the Git repository to work with
git_repo = GitConfig(
  url="https://github.com/python/cpython.git",  # Example: Python source
  branch="main",
  path="/workspace",
  shallow=True,  # Faster clone for large repositories
)

# Environment configuration
config = Environment(
  name="python-git-dev",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  # Git repository configuration
  git=git_repo,
  volumes=[
    # Mount Git configuration from host
    VolumeMount(source=str(Path.home() / ".gitconfig"), target="/root/.gitconfig"),
    # Optional: Mount SSH keys for private repositories
    # Note: Only include if you trust the container environment
    # VolumeMount(
    #     source=str(Path.home() / ".ssh"),
    #     target="/root/.ssh"
    # ),
    # Named volume for pip cache persistence
    VolumeMount(source="pip-cache", target="/root/.cache/pip"),
  ],
  # SSH access
  ports={
    22: {"HostPort": 2224},
    8000: {"HostPort": 8000},  # For web development
  },
  ssh=SSHConfig(port=22),
  environment={
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_TERMINAL_PROMPT": "0",  # Disable Git password prompts
  },
  # Resource allocation
  memory="4g",  # More memory for large repositories
  cpus=4.0,
)

# Note: After the environment starts, you can:
# 1. SSH in: python -m dev_env ssh python-git-dev
# 2. Install dependencies: pip install -r requirements.txt
# 3. Set up development tools: pip install pytest black mypy
