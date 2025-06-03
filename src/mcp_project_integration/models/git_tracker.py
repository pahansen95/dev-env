"""Git state tracking utilities for Claude Code integration"""

import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GitStateTracker:
  """Manages Git operations for session and task state tracking"""

  @staticmethod
  def run_git_command(args: List[str], cwd: Optional[Path] = None) -> str:
    """Execute Git command and return output"""
    try:
      result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=True,
      )
      return result.stdout.strip()
    except subprocess.CalledProcessError as e:
      logger.error(f"Git command failed: {e.stderr}")
      raise

  @classmethod
  def current_commit(cls) -> str:
    """Get current HEAD commit SHA"""
    return cls.run_git_command(["rev-parse", "HEAD"])

  @classmethod
  def current_branch(cls) -> str:
    """Get current branch name"""
    return cls.run_git_command(["branch", "--show-current"])

  @classmethod
  def is_clean(cls) -> bool:
    """Check if working directory is clean"""
    status = cls.run_git_command(["status", "--porcelain"])
    return len(status) == 0

  @classmethod
  def get_changes_since(cls, commit_sha: str) -> Dict[str, List[str]]:
    """Get file changes since given commit

    Returns dict with keys: added, modified, deleted
    """
    diff_output = cls.run_git_command(["diff", "--name-status", commit_sha, "HEAD"])

    changes = {"added": [], "modified": [], "deleted": []}

    if not diff_output:
      return changes

    for line in diff_output.splitlines():
      if not line.strip():
        continue

      parts = line.split("\t", 1)
      if len(parts) != 2:
        continue

      status, filepath = parts

      if status == "A":
        changes["added"].append(filepath)
      elif status == "M":
        changes["modified"].append(filepath)
      elif status == "D":
        changes["deleted"].append(filepath)

    return changes

  @classmethod
  def get_uncommitted_changes(cls) -> Dict[str, List[str]]:
    """Get current uncommitted changes

    Returns dict with keys: staged, unstaged, untracked
    """
    # Get staged changes
    staged_output = cls.run_git_command(["diff", "--cached", "--name-status"])

    # Get all changes (staged + unstaged)
    all_changes = cls.run_git_command(["status", "--porcelain"])

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

    Metadata is stored in commit message footer
    """
    # Stage all changes
    cls.run_git_command(["add", "-A"])

    # Build commit message with metadata
    full_message = message
    if metadata:
      full_message += "\n\n---\n"
      for key, value in metadata.items():
        full_message += f"{key}: {value}\n"

    # Create commit
    cls.run_git_command(["commit", "-m", full_message])
    return cls.current_commit()

  @classmethod
  def create_branch(cls, branch_name: str, checkout: bool = True) -> None:
    """Create new branch, optionally checking it out"""
    if checkout:
      cls.run_git_command(["checkout", "-b", branch_name])
    else:
      cls.run_git_command(["branch", branch_name])

  @classmethod
  def stash_changes(cls, message: str = "Auto-stash by Claude Code") -> Optional[str]:
    """Stash uncommitted changes if any exist"""
    if cls.is_clean():
      return None

    output = cls.run_git_command(["stash", "push", "-m", message])
    # Extract stash reference from output
    if "Saved working directory" in output:
      return cls.run_git_command(["stash", "list", "-1", "--format=%H"])
    return None

  @classmethod
  def parse_commit_metadata(cls, commit_sha: str) -> Dict[str, str]:
    """Extract metadata from commit message"""
    message = cls.run_git_command(["log", "-1", "--format=%B", commit_sha])

    metadata = {}
    in_metadata = False

    for line in message.splitlines():
      if line.strip() == "---":
        in_metadata = True
        continue

      if in_metadata and ":" in line:
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    return metadata

  @classmethod
  def get_file_diff(cls, filepath: str, from_commit: Optional[str] = None) -> str:
    """Get diff for specific file"""
    args = ["diff"]
    if from_commit:
      args.append(from_commit)
    args.extend(["--", filepath])

    return cls.run_git_command(args)
