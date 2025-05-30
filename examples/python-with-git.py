#!/usr/bin/env python3
"""
Python Development Environment with Git Integration

This example shows how to work with a Git repository:
- Clones a repository on environment startup
- Sets up Python development tools
- Configures Git credentials
- Mounts local SSH keys for private repos

Usage:
  # Public repository
  dev-env run examples/python-with-git.py

  # Private repository (ensure SSH keys are configured)
  dev-env run examples/python-with-git.py --ssh
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, GitConfig

# Configure the Git repository to work with
git_repo = GitConfig(
  url="https://github.com/example/my-python-project.git",
  branch="main",
  path="/workspace",
  shallow=True,  # Faster clone for large repositories
)

# Environment configuration
environment = Environment(
  name="python-git-dev",
  base_image="python:3.12-slim",
  git=git_repo,
  volumes=[
    # Mount home directory for Git config and SSH keys
    VolumeMount(source=str(Path.home() / ".gitconfig"), target="/root/.gitconfig", mode="ro"),
    # Optional: Mount SSH keys for private repositories
    VolumeMount(source=str(Path.home() / ".ssh"), target="/root/.ssh", mode="ro"),
    # Named volume for pip cache persistence
    VolumeMount(source="pip-cache", target="/root/.cache/pip", mode="rw"),
  ],
  working_dir="/workspace",
  command=["/bin/bash"],
  environment={
    "PYTHONUNBUFFERED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_TERMINAL_PROMPT": "0",  # Disable Git password prompts
  },
  init_commands=[
    # Install system dependencies
    "apt-get update && apt-get install -y git curl vim build-essential",
    # Configure Git (if not already configured via mounted .gitconfig)
    'git config --global user.name "${GIT_USER_NAME:-Developer}"',
    'git config --global user.email "${GIT_USER_EMAIL:-dev@example.com}"',
    # Install Python development tools
    "pip install --upgrade pip setuptools wheel",
    # Install project dependencies if requirements.txt exists
    "[ -f requirements.txt ] && pip install -r requirements.txt || true",
    # Install development tools
    "pip install ipython pytest pytest-cov black flake8 mypy pre-commit",
    # Set up pre-commit hooks if configured
    "[ -f .pre-commit-config.yaml ] && pre-commit install || true",
  ],
)
