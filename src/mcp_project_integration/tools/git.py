"""Git integration and version control tools"""

import logging
import subprocess

from ..server import mcp
from ..core import GitOperations

logger = logging.getLogger(__name__)


@mcp.tool()
def git_status() -> dict:
  """Get detailed git repository status"""
  logger.info("git_status called")

  try:
    # Get current branch
    branch = GitOperations.get_current_branch()

    # Get status information
    status_output = GitOperations.get_output(["status", "--porcelain=v1"])

    # Parse status output
    staged = []
    modified = []
    untracked = []

    for line in status_output.splitlines():
      if not line:
        continue
      status_code = line[:2]
      file_path = line[3:]

      if status_code[0] in "AMD":  # Added, Modified, or Deleted in index
        staged.append(file_path)
      if status_code[1] == "M":  # Modified in working tree
        modified.append(file_path)
      if status_code[1] == "D":  # Deleted in working tree
        modified.append(file_path)
      if status_code == "??":  # Untracked
        untracked.append(file_path)

    # Get commit info
    commit = GitOperations.get_output(["rev-parse", "--short", "HEAD"])

    # Check if detached HEAD
    try:
      GitOperations.get_output(["symbolic-ref", "-q", "HEAD"])
      detached = False
    except subprocess.CalledProcessError:
      detached = True

    return {
      "branch": branch if branch else "HEAD",
      "commit": commit,
      "detached": detached,
      "staged": staged,
      "modified": modified,
      "untracked": untracked,
      "clean": len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
    }
  except subprocess.CalledProcessError as e:
    error_msg = str(e)
    if hasattr(e, "stderr") and e.stderr:
      error_msg += f" - {e.stderr}"
    logger.error(f"Failed to get git status: {error_msg}")
    return {"error": error_msg}
  except Exception as e:
    logger.error(f"Unexpected error in git_status: {e}")
    return {"error": str(e)}


@mcp.tool()
def git_commit(message: str, files: list[str] = None) -> dict:
  """Create a git commit

  Args:
      message: Commit message
      files: Optional list of files to stage before committing

  Returns:
      Dict with status, commit hash, and message or error details
  """
  logger.info(f"git_commit called with message: {message}")

  try:
    # Stage files if specified
    if files:
      GitOperations.stage_files(files)

    # Check if there are changes to commit
    try:
      GitOperations.get_output(["diff-index", "--quiet", "--cached", "HEAD"])
      # No changes staged
      return {"status": "error", "error": "No changes staged for commit"}
    except subprocess.CalledProcessError:
      # Changes exist, proceed with commit
      pass

    # Create commit
    commit_hash = GitOperations.commit(message)

    return {"status": "success", "commit": commit_hash[:8], "message": message}
  except subprocess.CalledProcessError as e:
    error_msg = str(e)
    if hasattr(e, "stderr") and e.stderr:
      error_msg += f" - {e.stderr}"
    logger.error(f"Failed to commit: {error_msg}")
    return {"status": "error", "error": error_msg}


@mcp.tool()
def git_log(max_count: int = 10) -> list[dict]:
  """Get git commit history

  Args:
      max_count: Maximum number of commits to return

  Returns:
      List of commit dictionaries or error dict
  """
  logger.info(f"git_log called with max_count={max_count}")

  try:
    # Validate max_count
    if max_count < 1:
      max_count = 1
    elif max_count > 1000:
      max_count = 1000

    # Get log with custom format
    log_format = "%H|%h|%an|%ae|%ad|%s"
    log_output = GitOperations.get_output(["log", f"--max-count={max_count}", f"--format={log_format}", "--date=iso"])

    if not log_output:
      return []

    commits = []
    for line in log_output.splitlines():
      if not line:
        continue
      parts = line.split("|", 5)
      if len(parts) >= 6:
        commits.append(
          {
            "hash": parts[0],
            "short_hash": parts[1],
            "author": parts[2],
            "email": parts[3],
            "date": parts[4],
            "message": parts[5],
          }
        )

    return commits
  except subprocess.CalledProcessError as e:
    error_msg = str(e)
    if hasattr(e, "stderr") and e.stderr:
      error_msg += f" - {e.stderr}"
    logger.error(f"Failed to get git log: {error_msg}")
    return [{"error": error_msg}]
  except Exception as e:
    logger.error(f"Unexpected error in git_log: {e}")
    return [{"error": str(e)}]


@mcp.tool()
def git_diff(file: str = None, staged: bool = False) -> str:
  """Get git diff output

  Args:
      file: Optional specific file to diff
      staged: Whether to show staged changes (--cached)

  Returns:
      Diff output as string, or error message
  """
  logger.info(f"git_diff called for file={file}, staged={staged}")

  try:
    args = ["diff"]

    # Add appropriate flags
    if staged:
      args.append("--cached")

    # Add file if specified
    if file:
      # Validate file path exists in repo
      try:
        GitOperations.get_output(["ls-files", "--error-unmatch", file])
      except subprocess.CalledProcessError:
        return f"Error: File '{file}' is not tracked by git"
      args.append(file)

    diff_output = GitOperations.get_output(args)
    return diff_output if diff_output else "No differences found"

  except subprocess.CalledProcessError as e:
    error_msg = f"Failed to get diff: {str(e)}"
    if hasattr(e, "stderr") and e.stderr:
      error_msg += f" - {e.stderr}"
    logger.error(error_msg)
    return f"Error: {error_msg}"
  except Exception as e:
    logger.error(f"Unexpected error in git_diff: {e}")
    return f"Error: {str(e)}"
