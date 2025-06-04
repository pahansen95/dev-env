"""Project status and health monitoring tools"""

import logging
import subprocess
import sys
from datetime import datetime

from ..server import mcp
from ..core import find_git_root, get_git_project_name, GitOperations

logger = logging.getLogger(__name__)


@mcp.tool()
def status() -> dict:
  """Get project health status and basic information"""
  logger.info("status tool called")

  status_info = {"health": "ok", "timestamp": datetime.utcnow().isoformat() + "Z", "errors": []}

  try:
    # Basic git information
    git_root = find_git_root()
    status_info["project"] = {"name": get_git_project_name(), "root": str(git_root), "root_exists": git_root.exists()}

    # Git status
    try:
      branch = GitOperations.get_current_branch()
      commit = GitOperations.get_output(["rev-parse", "--short", "HEAD"])

      # Check for uncommitted changes
      git_status = GitOperations.get_output(["status", "--porcelain"])
      is_clean = len(git_status) == 0

      status_info["git"] = {
        "branch": branch,
        "commit": commit,
        "clean": is_clean,
        "changes": len(git_status.splitlines()) if git_status else 0,
      }
    except subprocess.CalledProcessError as e:
      status_info["errors"].append(f"Git error: {str(e)}")
      status_info["git"] = {"error": "Unable to get git status"}

    # Python environment check
    venv_path = git_root / ".venv"
    status_info["environment"] = {
      "python": sys.version.split()[0],
      "venv_exists": venv_path.exists(),
      "venv_active": sys.prefix == str(venv_path),
    }

    # Basic project structure
    readme_exists = (git_root / "README.md").exists()
    src_exists = (git_root / "src").exists()

    status_info["structure"] = {
      "has_readme": readme_exists,
      "has_src": src_exists,
      "python_files": len(list(git_root.glob("**/*.py"))),
    }

  except subprocess.CalledProcessError:
    status_info["health"] = "error"
    status_info["errors"].append("Not in a git repository")
  except Exception as e:
    status_info["health"] = "error"
    status_info["errors"].append(f"Unexpected error: {str(e)}")
    logger.exception("Error in status tool")

  # Set health to warning if there are non-fatal errors
  if status_info["errors"] and status_info["health"] == "ok":
    status_info["health"] = "warning"

  return status_info
