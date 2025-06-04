"""Project-specific utilities and safety mechanisms

# Project Boundary System

The Project Boundary System provides a security and organizational framework that
ensures all file operations remain within the Git repository boundaries. It serves
as a protective layer preventing accidental or malicious operations from affecting
files outside the project scope.

## Core Principles

**Git-Centric Boundaries**
All operations are scoped to the Git repository root, using Git's own understanding
of project boundaries as the authoritative source. This ensures consistency with
version control and prevents operations on untracked external files.

**Path Validation Strategy**
- Resolve symbolic links to prevent escape via symlink manipulation
- Validate parent directory existence for new file creation
- Maintain original paths for user clarity while validating resolved paths

**Project Identity**
The system derives project identity from Git configuration, preferring:
1. Remote origin repository name (for cloned projects)
2. Local directory name (for local-only projects)

## Safety Mechanisms

**Directory Traversal Prevention**
All paths are validated to ensure they resolve within the Git repository,
preventing classic "../../../etc/passwd" style attacks or accidental operations
outside project boundaries.

**Existence Validation**
Optional validation ensures operations only target existing files when required,
preventing errors from typos or incorrect paths.

## Implementation Philosophy

The module prioritizes safety without sacrificing usability:
- Clear error messages guide users to correct usage
- Git integration provides natural, familiar boundaries
- Path validation is transparent to valid operations
- Security checks don't impede normal workflow

This approach transforms potentially dangerous file operations into safe,
predictable actions within well-defined project boundaries.
"""

import subprocess
from pathlib import Path
import logging

from .utils import GitOperations

logger = logging.getLogger(__name__)


def find_git_root() -> Path:
  """Find the git project root directory

  Returns:
      Path object pointing to the repository root

  Raises:
      subprocess.CalledProcessError: Not in a git repository
  """
  root_path = GitOperations.get_repository_root()
  return root_path


def get_git_project_name() -> str:
  """Get project name from git (remote origin or directory name)

  Attempts to extract project name from remote origin URL,
  falling back to directory name if no remote is configured.

  Returns:
      Project name string
  """
  # Try to get from remote origin
  try:
    remote_url = GitOperations.get_output(["config", "--get", "remote.origin.url"])

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


def get_safe_path(path_str: str, must_exist: bool = False) -> Path:
  """Validate and return a safe path within the git project

  Ensures the requested path remains within project boundaries,
  preventing directory traversal attacks and accidental operations
  outside the repository.

  Args:
      path_str: Path string relative to git root
      must_exist: Whether the path must already exist

  Returns:
      Path object within project boundaries

  Raises:
      ValueError: Path escapes project directory
      FileNotFoundError: Path doesn't exist when must_exist=True
  """
  git_root = find_git_root()

  # Resolve git root to handle its potential symlinks
  git_root_resolved = git_root.resolve()

  # Construct target path
  target_path = git_root / path_str

  # Resolve the path (follows symlinks)
  if must_exist:
    # This will raise if path doesn't exist
    resolved_path = target_path.resolve(strict=True)
  else:
    # Parent must exist for non-existent paths
    resolved_path = target_path.resolve(strict=False)
    if not resolved_path.parent.exists():
      raise FileNotFoundError(f"Parent directory of {path_str} does not exist")

  # Verify the resolved path is within project boundaries
  try:
    resolved_path.relative_to(git_root_resolved)
  except ValueError:
    raise ValueError(f"Path '{path_str}' resolves outside project directory. Resolved to: {resolved_path}")

  # Return the original target_path (not resolved) for consistency
  # but we've validated it's safe
  return target_path
