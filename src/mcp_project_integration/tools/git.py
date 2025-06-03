"""Git integration and version control tools"""

import logging
import subprocess

from ..server import mcp
from ..utils import run_git_command

logger = logging.getLogger(__name__)


@mcp.tool()
def git_status() -> dict:
  """Get detailed git repository status"""
  logger.info("git_status called")

  try:
    # Get current branch
    branch = run_git_command(["branch", "--show-current"])

    # Get status information
    status_output = run_git_command(["status", "--porcelain=v1"])

    # Parse status output
    staged = []
    modified = []
    untracked = []

    for line in status_output.splitlines():
      if not line:
        continue
      status_code = line[:2]
      file_path = line[3:]

      if status_code[0] in "AM":  # Added or Modified in index
        staged.append(file_path)
      if status_code[1] == "M":  # Modified in working tree
        modified.append(file_path)
      if status_code == "??":  # Untracked
        untracked.append(file_path)

    # Get commit info
    commit = run_git_command(["rev-parse", "--short", "HEAD"])

    return {
      "branch": branch,
      "commit": commit,
      "staged": staged,
      "modified": modified,
      "untracked": untracked,
      "clean": len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
    }
  except Exception as e:
    logger.error(f"Failed to get git status: {e}")
    return {"error": str(e)}


@mcp.tool()
def git_commit(message: str, files: list[str] = None) -> dict:
  """Create a git commit"""
  logger.info(f"git_commit called with message: {message}")

  try:
    # Stage files if specified
    if files:
      for file in files:
        run_git_command(["add", file])

    # Create commit
    run_git_command(["commit", "-m", message])

    # Get new commit info
    commit_hash = run_git_command(["rev-parse", "--short", "HEAD"])

    return {"status": "success", "commit": commit_hash, "message": message}
  except subprocess.CalledProcessError as e:
    logger.error(f"Failed to commit: {e}")
    return {"status": "error", "error": str(e), "stderr": e.stderr}


@mcp.tool()
def git_log(max_count: int = 10) -> list[dict]:
  """Get git commit history"""
  logger.info(f"git_log called with max_count={max_count}")

  try:
    # Get log with custom format
    log_format = "%H|%h|%an|%ae|%ad|%s"
    log_output = run_git_command(["log", f"--max-count={max_count}", f"--format={log_format}", "--date=iso"])

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
  except Exception as e:
    logger.error(f"Failed to get git log: {e}")
    return [{"error": str(e)}]


@mcp.tool()
def git_diff(file: str = None, staged: bool = False) -> str:
  """Get git diff output"""
  logger.info(f"git_diff called for file={file}, staged={staged}")

  try:
    args = ["diff"]

    if staged:
      args.append("--cached")

    if file:
      args.append(file)

    diff_output = run_git_command(args)
    return diff_output if diff_output else "No differences found"

  except Exception as e:
    logger.error(f"Failed to get diff: {e}")
    return f"Error: {str(e)}"
