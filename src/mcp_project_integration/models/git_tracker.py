"""Git state tracking for Claude Code integration

This module provides a thin wrapper around core Git operations, adding
session and task-specific functionality for tracking development progress.
"""

from datetime import datetime
from typing import Dict, List, Optional
import logging

from ..core.utils import GitOperations

logger = logging.getLogger(__name__)


class GitStateTracker:
  """Tracks Git state changes for coding sessions and tasks

  Extends core Git operations with metadata management and state capture
  functionality specific to Claude Code integration workflows.
  """

  @classmethod
  def current_commit(cls) -> str:
    """Get current HEAD commit SHA"""
    return GitOperations.get_current_commit()

  @classmethod
  def current_branch(cls) -> str:
    """Get current branch name"""
    return GitOperations.get_current_branch()

  @classmethod
  def is_clean(cls) -> bool:
    """Check if working directory is clean"""
    return GitOperations.is_clean()

  @classmethod
  def get_changes_since(cls, commit_sha: str) -> Dict[str, List[str]]:
    """Get file changes since given commit

    Returns dict with keys: added, modified, deleted, renamed
    """
    return GitOperations.get_file_changes(from_ref=commit_sha, to_ref="HEAD")

  @classmethod
  def get_uncommitted_changes(cls) -> Dict[str, List[str]]:
    """Get current uncommitted changes

    Returns dict with keys: staged, unstaged, untracked
    """
    # Get staged changes
    staged_output = GitOperations.get_output(["diff", "--cached", "--name-status"])

    # Get all changes
    all_changes = GitOperations.get_output(["status", "--porcelain"])

    changes = {"staged": [], "unstaged": [], "untracked": []}

    # Parse staged changes
    for line in staged_output.splitlines():
      if not line.strip():
        continue
      parts = line.split("\t", 1)
      if len(parts) == 2:
        changes["staged"].append(parts[1])

    # Parse all changes
    for line in all_changes.splitlines():
      if not line.strip():
        continue

      status = line[:2]
      filepath = line[3:]

      if status == "??":
        changes["untracked"].append(filepath)
      elif status[1] != " " and filepath not in changes["staged"]:
        changes["unstaged"].append(filepath)

    return changes

  @classmethod
  def capture_state(cls) -> Dict[str, any]:
    """Capture current Git state snapshot"""
    return {
      "commit": cls.current_commit(),
      "branch": cls.current_branch(),
      "timestamp": datetime.now(),
      "is_clean": cls.is_clean(),
    }

  @classmethod
  def commit(cls, message: str, metadata: Optional[Dict] = None) -> str:
    """Create commit with optional metadata

    Metadata is stored in commit message footer using the format:
    ---
    key: value
    """
    # Stage all changes
    GitOperations.stage_all()

    # Build metadata body
    body = None
    if metadata:
      body = "---\n"
      for key, value in metadata.items():
        body += f"{key}: {value}\n"

    # Create commit
    return GitOperations.commit(message, body)

  @classmethod
  def create_branch(cls, branch_name: str, checkout: bool = True) -> None:
    """Create new branch, optionally checking it out"""
    GitOperations.create_branch(branch_name, checkout)

  @classmethod
  def stash_changes(cls, message: str = "Auto-stash by Claude Code") -> Optional[str]:
    """Stash uncommitted changes if any exist"""
    return GitOperations.stash(message)

  @classmethod
  def parse_commit_metadata(cls, commit_sha: str) -> Dict[str, str]:
    """Extract metadata from commit message"""
    return GitOperations.get_commit_metadata(commit_sha)

  @classmethod
  def get_file_diff(cls, filepath: Optional[str], from_commit: Optional[str] = None) -> str:
    """Get diff for specific file or all files"""
    args = ["diff"]

    if from_commit:
      args.append(from_commit)

    if filepath:
      args.extend(["--", filepath])

    return GitOperations.get_output(args)
