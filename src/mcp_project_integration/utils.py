"""Shared utilities for MCP Project Integration"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


# Git utility functions
def run_git_command(args, cwd=None):
  """Run a git command and return output"""
  result = subprocess.run(
    ["git"] + args,
    capture_output=True,
    text=True,
    cwd=cwd,
    check=True,  # Fail fast on git errors
  )
  return result.stdout.strip()


def find_git_root():
  """Find the git project root directory"""
  return Path(run_git_command(["rev-parse", "--show-toplevel"]))


def get_git_project_name():
  """Get project name from git (remote origin or directory name)"""
  # Try to get from remote origin
  try:
    remote_url = run_git_command(["config", "--get", "remote.origin.url"])
    # Extract project name from URL
    if remote_url.endswith(".git"):
      remote_url = remote_url[:-4]

    # Get the last part of the URL
    project_name = remote_url.split("/")[-1]
    if ":" in project_name:  # SSH URL format
      project_name = project_name.split(":")[-1]

    return project_name
  except subprocess.CalledProcessError:
    # No remote, use directory name
    return find_git_root().name


# Path validation helper
def get_safe_path(path_str, must_exist=False):
  """Validate and return a safe path within the git project"""
  git_root = find_git_root()
  target_path = (git_root / path_str).resolve()

  # Ensure path is within project
  target_path.relative_to(git_root)

  # Check existence if required
  if must_exist:
    target_path.stat()

  return target_path


# Logging configuration
def add_file_logging(log_file):
  """Add file handler to existing logger"""
  # Create log directory if needed
  log_path = Path(log_file)
  log_path.parent.mkdir(parents=True, exist_ok=True)

  # Create file handler with same format
  file_handler = logging.FileHandler(log_file, mode="a")
  file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
  file_handler.setLevel(logging.DEBUG)  # Capture all levels

  # Add to root logger to capture all logs
  root_logger = logging.getLogger()
  root_logger.addHandler(file_handler)

  # Force immediate write
  logger.info(f"=== MCP Server Started - PID: {os.getpid()} ===")
  file_handler.flush()
