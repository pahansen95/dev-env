"""Git operations wrapper

# Git Operations Abstraction

The GitOperations class provides a unified interface for Git subprocess commands,
abstracting the complexity of command-line interactions into a type-safe Python API.
It serves as the foundational layer for all version control operations within the
MCP Project Integration system.

## Architecture

Git operations are fundamentally subprocess executions that require careful handling
of stdout, stderr, and return codes. This abstraction layer transforms these raw
interactions into predictable, well-typed Python methods with consistent error
handling and output parsing.

Key characteristics:
- Subprocess command encapsulation
- Consistent error propagation
- Structured output parsing
- Automatic logging integration

## Design Principles

**Type Safety**
All methods return strongly-typed results rather than raw strings, enabling
compile-time verification and IDE support for Git operations.

**Error Transparency**
Git command failures are captured with full context (stdout, stderr, exit codes)
and propagated as Python exceptions with meaningful error messages.

**Minimal Abstraction**
The interface closely mirrors Git's command-line structure, making it intuitive
for developers familiar with Git while providing Python-native conveniences.

**Stateless Operations**
Each method is stateless and side-effect free (beyond Git operations), enabling
safe concurrent usage and predictable behavior.

## Implementation Philosophy

This module prioritizes reliability and clarity over feature completeness. Rather
than wrapping every Git command, it provides essential operations needed for
automated development workflows while maintaining direct Git command access for
edge cases.

The GitOperations abstraction transforms error-prone string manipulation of Git
commands into reliable, testable Python methods that form the foundation for
higher-level version control workflows.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GitOperations:
  """Manages Git subprocess operations

  Provides a unified interface for Git commands with consistent error handling,
  output parsing, and logging. All operations are executed in the context of
  a Git repository.
  """

  @staticmethod
  def run_command(args: List[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Execute Git command and return result

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for command execution
        check: Raise exception on non-zero exit code

    Returns:
        Completed process with stdout, stderr, and return code

    Raises:
        subprocess.CalledProcessError: Command failed and check=True
    """
    cmd = ["git"] + args

    try:
      result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=check)
      return result
    except subprocess.CalledProcessError as e:
      logger.error(f"Git command failed: {' '.join(cmd)}")
      logger.error(f"Error output: {e.stderr}")
      raise

  @classmethod
  def get_output(cls, args: List[str], cwd: Optional[Path] = None) -> str:
    """Execute Git command and return stdout

    Convenience method for commands that return text output.
    """
    result = cls.run_command(args, cwd)
    return result.stdout.strip()

  @classmethod
  def get_repository_root(cls, cwd: Optional[Path] = None) -> Path:
    """Find the root directory of the Git repository"""
    output = cls.get_output(["rev-parse", "--show-toplevel"], cwd)
    return Path(output)

  @classmethod
  def get_current_commit(cls, cwd: Optional[Path] = None) -> str:
    """Get the SHA of the current HEAD commit"""
    return cls.get_output(["rev-parse", "HEAD"], cwd)

  @classmethod
  def get_current_branch(cls, cwd: Optional[Path] = None) -> str:
    """Get the name of the current branch"""
    return cls.get_output(["branch", "--show-current"], cwd)

  @classmethod
  def is_repository(cls, path: Path) -> bool:
    """Check if path is inside a Git repository"""
    try:
      cls.run_command(["rev-parse", "--git-dir"], cwd=path)
      return True
    except subprocess.CalledProcessError:
      return False

  @classmethod
  def is_clean(cls, cwd: Optional[Path] = None) -> bool:
    """Check if working directory has no uncommitted changes"""
    output = cls.get_output(["status", "--porcelain"], cwd)
    return len(output) == 0

  @classmethod
  def get_file_changes(
    cls, from_ref: Optional[str] = None, to_ref: Optional[str] = None, cwd: Optional[Path] = None
  ) -> Dict[str, List[str]]:
    """Get categorized file changes between references

    Args:
        from_ref: Starting reference (commit/branch/tag)
        to_ref: Ending reference (defaults to HEAD)
        cwd: Working directory

    Returns:
        Dictionary with keys: added, modified, deleted, renamed
    """
    args = ["diff", "--name-status"]

    if from_ref:
      args.append(from_ref)
    if to_ref:
      args.append(to_ref)

    output = cls.get_output(args, cwd)

    changes = {"added": [], "modified": [], "deleted": [], "renamed": []}

    if not output:
      return changes

    for line in output.splitlines():
      if not line.strip():
        continue

      parts = line.split("\t", 2)
      if len(parts) < 2:
        continue

      status = parts[0]

      if status == "A":
        changes["added"].append(parts[1])
      elif status == "M":
        changes["modified"].append(parts[1])
      elif status == "D":
        changes["deleted"].append(parts[1])
      elif status.startswith("R"):
        # Renamed files have old and new paths
        if len(parts) == 3:
          changes["renamed"].append({"from": parts[1], "to": parts[2]})

    return changes

  @classmethod
  def stage_files(cls, paths: List[str], cwd: Optional[Path] = None) -> None:
    """Stage files for commit

    Args:
        paths: List of file paths to stage
        cwd: Working directory
    """
    if not paths:
      return

    cls.run_command(["add"] + paths, cwd)
    logger.debug(f"Staged {len(paths)} files")

  @classmethod
  def stage_all(cls, cwd: Optional[Path] = None) -> None:
    """Stage all changes including new files"""
    cls.run_command(["add", "-A"], cwd)
    logger.debug("Staged all changes")

  @classmethod
  def commit(cls, message: str, body: Optional[str] = None, cwd: Optional[Path] = None) -> str:
    """Create a commit with the staged changes

    Args:
        message: Commit message header
        body: Optional commit message body
        cwd: Working directory

    Returns:
        SHA of the created commit
    """
    full_message = message
    if body:
      full_message = f"{message}\n\n{body}"

    cls.run_command(["commit", "-m", full_message], cwd)
    commit_sha = cls.get_current_commit(cwd)

    logger.info(f"Created commit {commit_sha[:8]}: {message}")
    return commit_sha

  @classmethod
  def create_branch(cls, branch_name: str, checkout: bool = True, cwd: Optional[Path] = None) -> None:
    """Create a new branch

    Args:
        branch_name: Name for the new branch
        checkout: Switch to the new branch after creation
        cwd: Working directory
    """
    if checkout:
      cls.run_command(["checkout", "-b", branch_name], cwd)
      logger.info(f"Created and checked out branch: {branch_name}")
    else:
      cls.run_command(["branch", branch_name], cwd)
      logger.info(f"Created branch: {branch_name}")

  @classmethod
  def stash(
    cls, message: Optional[str] = None, include_untracked: bool = True, cwd: Optional[Path] = None
  ) -> Optional[str]:
    """Stash uncommitted changes

    Args:
        message: Optional stash message
        include_untracked: Include untracked files in stash
        cwd: Working directory

    Returns:
        Stash reference if changes were stashed, None if working directory was clean
    """
    if cls.is_clean(cwd):
      return None

    args = ["stash", "push"]
    if message:
      args.extend(["-m", message])
    if include_untracked:
      args.append("-u")

    output = cls.get_output(args, cwd)

    # Extract stash reference
    if "Saved working directory" in output:
      stash_ref = cls.get_output(["stash", "list", "-1", "--format=%H"], cwd)
      logger.info(f"Created stash: {message or 'Unnamed stash'}")
      return stash_ref

    return None

  @classmethod
  def stash_pop(cls, cwd: Optional[Path] = None) -> None:
    """Apply and remove the most recent stash"""
    cls.run_command(["stash", "pop"], cwd)
    logger.info("Applied and removed stash")

  @classmethod
  def reset_hard(cls, ref: str, cwd: Optional[Path] = None) -> None:
    """Hard reset to a specific reference

    Warning: This discards all uncommitted changes
    """
    cls.run_command(["reset", "--hard", ref], cwd)
    logger.warning(f"Hard reset to {ref}")

  @classmethod
  def get_commit_metadata(cls, ref: str, cwd: Optional[Path] = None) -> Dict[str, str]:
    """Extract metadata from a commit message

    Parses commit messages with metadata in the format:
    ```
    Commit message

    ---
    key1: value1
    key2: value2
    ```
    """
    message = cls.get_output(["log", "-1", "--format=%B", ref], cwd)

    metadata = {}
    in_metadata_section = False

    for line in message.splitlines():
      if line.strip() == "---":
        in_metadata_section = True
        continue

      if in_metadata_section and ":" in line:
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    return metadata
