"""Project status and health monitoring tools"""

import logging
import subprocess
import sys
from datetime import datetime

from ..server import mcp
from ..core import find_git_root, get_git_project_name, GitOperations, document_tool

logger = logging.getLogger(__name__)


TOOL_PREFIX = "project"


@document_tool(
  name="project_status",
  purpose="Establish project context by checking health, Git state, and environment",
  category="Project Management",
  operational_model="""
  Inspects project root, Git repository state, Python environment, and basic
  structure. Aggregates health indicators into overall status assessment.
  """,
  usage_scenarios=[
    {
      "condition": "Starting a new development session",
      "rationale": "Establishes baseline understanding of project state",
    },
    {
      "condition": "Before making commits or structural changes",
      "rationale": "Verifies clean working directory and proper environment",
    },
    {
      "condition": "Debugging environment issues",
      "rationale": "Identifies missing dependencies or configuration problems",
    },
  ],
  examples=[
    {
      "title": "Check project health",
      "code": "status = project_status()",
      "explanation": "Basic health check at session start",
      "complexity": 1,
    },
    {
      "title": "Verify clean state before commit",
      "code": """status = project_status()
if not status['git']['clean']:
    print(f"Uncommitted changes: {status['git']['changes']} files")""",
      "explanation": "Ensure working directory is clean",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Not in git repository",
      "cause": "Tool invoked outside Git-managed directory",
      "diagnosis": "Check current working directory with 'pwd'",
      "recovery": "Navigate to project root or initialize Git",
      "state_impact": "Returns error status, no other operations attempted",
    }
  ],
  performance={
    "time_complexity": "O(n) with number of Python files",
    "memory_usage": "Minimal - metadata only",
    "concurrency": "Thread-safe",
  },
  see_also={"git_status": "Detailed Git repository information", "search_files": "Find specific project files"},
  composition=["project_status → file_read → git_commit", "project_status → session_start"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_status",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def status() -> dict:
  """Get project health status and basic information.

  Provides comprehensive project context including Git state, Python environment,
  and project structure. This is typically the first tool to call when establishing
  project context.

  Use when:
  - Starting a new development session
  - Verifying project configuration
  - Checking for uncommitted changes
  - Understanding project structure

  Returns:
      Dictionary containing:
      - health: Overall status ("ok", "warning", "error")
      - timestamp: ISO 8601 UTC timestamp
      - project: Name, root path, and existence check
      - git: Branch, commit hash, cleanliness, change count
      - environment: Python version, venv status
      - structure: README/src existence, Python file count
      - errors: List of non-fatal issues encountered

  Common patterns:
  - health="ok" with clean=false: Working directory has uncommitted changes
  - health="warning": Non-fatal errors detected (check errors list)
  - health="error": Not in a Git repository or critical failure

  Example response:
  {"health": "ok", "git": {"branch": "main", "clean": true}, ...}
  """
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
