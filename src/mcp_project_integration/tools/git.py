"""Git integration and version control tools"""

import logging
import subprocess

from ..server import mcp
from ..core import GitOperations, document_tool

logger = logging.getLogger(__name__)


TOOL_PREFIX = "git"


@document_tool(
  name="git_status",
  purpose="Analyze repository state including branches, commits, and working directory changes",
  category="Git Operations",
  operational_model="""
  Parses git status output into structured data, categorizing files by their
  state (staged, modified, untracked). Detects detached HEAD and empty repos.
  """,
  usage_scenarios=[
    {"condition": "Before making commits", "rationale": "Understand what changes will be included"},
    {
      "condition": "Checking for clean working directory",
      "rationale": "Ensure no uncommitted changes before operations",
    },
    {"condition": "Understanding repository state", "rationale": "Get comprehensive view of current work"},
  ],
  examples=[
    {
      "title": "Check repository state",
      "code": "status = git_status()",
      "explanation": "Get full repository status",
      "complexity": 1,
    },
    {
      "title": "Verify clean state",
      "code": """status = git_status()
if status['clean']:
    print('Ready to switch branches')""",
      "explanation": "Ensure no pending changes",
      "complexity": 2,
    },
    {
      "title": "List uncommitted files",
      "code": """status = git_status()
all_changes = status['staged'] + status['modified'] + status['untracked']
print(f"Uncommitted files: {all_changes}")""",
      "explanation": "Gather all changed files",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Not in repository",
      "cause": "Called outside git repository",
      "diagnosis": "Check current directory",
      "recovery": "Navigate to git repository",
      "state_impact": "Returns error dict",
    }
  ],
  performance={
    "time_complexity": "O(n) with tracked files",
    "memory_usage": "Minimal - metadata only",
    "concurrency": "Thread-safe",
  },
  see_also={"git_diff": "View actual changes", "git_commit": "Commit staged changes"},
  composition=["git_status → git_commit", "git_status → git_diff"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_status",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def git_status() -> dict:
  """Get detailed git repository status.

  Provides comprehensive view of repository state including current branch,
  commit, and working directory changes. Parses git status into structured data.

  Returns:
      Dictionary containing:
      - branch: Current branch name or "HEAD" if detached
      - commit: Short commit hash (8 chars)
      - detached: Boolean indicating detached HEAD state
      - staged: List of files staged for commit
      - modified: List of modified files in working tree
      - untracked: List of untracked files
      - clean: Boolean indicating no changes

  Use when:
  - Checking for uncommitted changes before operations
  - Understanding current repository state
  - Preparing commit messages
  - Validating clean working directory

  Error handling:
  - Returns {"error": "message"} if not in git repository
  - Handles detached HEAD states gracefully
  - Works with empty repositories
  """
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


@document_tool(
  name="git_commit",
  purpose="Create permanent commits in git history with optional file staging",
  category="Git Operations",
  operational_model="""
  Optionally stages specified files, then creates a commit with the provided
  message. Requires at least one staged change. Uses system git configuration
  for author information.
  """,
  usage_scenarios=[
    {"condition": "Saving completed work", "rationale": "Create permanent checkpoint in history"},
    {"condition": "Before risky operations", "rationale": "Enable rollback if needed"},
    {"condition": "Documenting logical changes", "rationale": "Track project evolution with clear messages"},
  ],
  anti_patterns=[
    {
      "condition": "Committing without testing",
      "reason": "May introduce broken state",
      "alternative": "Test changes before committing",
    },
    {
      "condition": "Large monolithic commits",
      "reason": "Difficult to review and revert",
      "alternative": "Make focused, atomic commits",
    },
  ],
  examples=[
    {
      "title": "Commit all staged changes",
      "code": 'git_commit("Fix authentication bug")',
      "explanation": "Commits pre-staged changes",
      "complexity": 1,
    },
    {
      "title": "Stage and commit specific files",
      "code": 'git_commit("Add user model", ["models/user.py", "tests/test_user.py"])',
      "explanation": "Stage files then commit",
      "complexity": 2,
    },
    {
      "title": "Commit with validation",
      "code": """result = git_commit("Update config")
if result['status'] == 'success':
    print(f"Created commit {result['commit']}")""",
      "explanation": "Handle commit result",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "No changes staged",
      "cause": "Nothing to commit",
      "diagnosis": "Check git_status for changes",
      "recovery": "Stage files or make modifications",
      "state_impact": "No commit created",
    },
    {
      "error_type": "Invalid file paths",
      "cause": "Specified files don't exist",
      "diagnosis": "Verify file paths",
      "recovery": "Correct file list",
      "state_impact": "No commit created",
    },
  ],
  performance={
    "time_complexity": "O(n) with file count",
    "memory_usage": "Proportional to changes",
    "concurrency": "Not safe - single writer",
  },
  see_also={"git_status": "Check what will be committed", "git_log": "View commit history"},
  composition=["file_write → git_status → git_commit"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_commit",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,  # Creates new commits
    "openWorldHint": False,
  },
)
def git_commit(message: str, files: list[str] = None) -> dict:
  """Create a git commit

  Args:
      message: Commit message
      files: Optional list of files to stage before committing

  Returns:
      Dict with status, commit hash, and message or error details

  Use when:
  - Saving work progress
  - Creating restore points
  - Documenting completed changes
  - Before risky operations

  Behavior:
  - Stages specified files before committing
  - Commits all staged changes if no files specified
  - Requires at least one staged change
  - Uses current user's git configuration

  Side effects:
  - Creates permanent commit in git history
  - Updates HEAD and current branch
  - Triggers any configured git hooks

  Return format:
  - Success: {"status": "success", "commit": "abc12345", "message": "..."}
  - Error: {"status": "error", "error": "No changes staged for commit"}

  Example: git_commit("Add user authentication", ["auth.py", "tests/test_auth.py"])
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


@document_tool(
  name="git_log",
  purpose="Retrieve commit history with author and message information",
  category="Git Operations",
  operational_model="""
  Fetches commit history in reverse chronological order, parsing git log output
  into structured format. Limited to prevent excessive memory usage.
  """,
  usage_scenarios=[
    {"condition": "Reviewing recent changes", "rationale": "Understand project evolution"},
    {"condition": "Finding specific commits", "rationale": "Locate changes by message or author"},
    {"condition": "Generating changelogs", "rationale": "Extract commit information for documentation"},
  ],
  examples=[
    {
      "title": "Get recent commits",
      "code": "commits = git_log(10)",
      "explanation": "Fetch last 10 commits",
      "complexity": 1,
    },
    {
      "title": "Find commits by author",
      "code": """commits = git_log(50)
my_commits = [c for c in commits if 'john' in c['author'].lower()]""",
      "explanation": "Filter commits by author",
      "complexity": 2,
    },
    {
      "title": "Extract commit messages",
      "code": """commits = git_log(20)
messages = [c['message'] for c in commits if 'fix' in c['message'].lower()]""",
      "explanation": "Find fix commits",
      "complexity": 2,
    },
  ],
  performance={
    "time_complexity": "O(n) with commit count",
    "memory_usage": "Proportional to max_count",
    "concurrency": "Thread-safe",
  },
  see_also={"git_status": "Current repository state", "git_diff": "View changes in commits"},
  composition=["git_commit → git_log"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_log",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def git_log(max_count: int = 10) -> list[dict]:
  """Get git commit history

  Args:
      max_count: Maximum number of commits to return

  Returns:
      List of commit dictionaries or error dict

  Commit format:
      - hash: Full commit SHA
      - short_hash: Abbreviated commit SHA
      - author: Author name
      - email: Author email
      - date: ISO format timestamp
      - message: Commit message

  Use when:
  - Reviewing recent changes
  - Finding specific commits
  - Understanding project history
  - Generating changelogs

  Constraints:
  - max_count limited to 1-1000
  - Returns empty list for new repositories
  - Ordered by recency (newest first)
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


@document_tool(
  name="git_diff",
  purpose="Show detailed changes in working directory or staging area",
  category="Git Operations",
  operational_model="""
  Generates unified diff output showing line-by-line changes. Can show unstaged
  changes, staged changes, or specific file diffs. Empty for no changes.
  """,
  usage_scenarios=[
    {"condition": "Reviewing changes before commit", "rationale": "Understand exact modifications"},
    {"condition": "Generating patches", "rationale": "Create applicable diff output"},
    {"condition": "Validating expected changes", "rationale": "Ensure correct modifications"},
  ],
  examples=[
    {
      "title": "View all unstaged changes",
      "code": "diff = git_diff()",
      "explanation": "See working directory changes",
      "complexity": 1,
    },
    {
      "title": "View staged changes",
      "code": "diff = git_diff(staged=True)",
      "explanation": "See what will be committed",
      "complexity": 1,
    },
    {
      "title": "Check specific file",
      "code": 'diff = git_diff("src/main.py")',
      "explanation": "Diff single file",
      "complexity": 2,
    },
    {
      "title": "Save diff as patch",
      "code": """diff = git_diff()
if diff != "No differences found":
    file_write("changes.patch", diff)""",
      "explanation": "Export diff for later use",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "File not tracked",
      "cause": "Specified file not in git",
      "diagnosis": "File may be untracked",
      "recovery": "Add file to git first",
      "state_impact": "Returns error message",
    }
  ],
  performance={
    "time_complexity": "O(n) with change size",
    "memory_usage": "Full diff in memory",
    "concurrency": "Thread-safe",
  },
  see_also={"git_status": "List changed files", "patch_apply": "Apply diff output"},
  composition=["git_diff → patch_apply", "file_write → git_diff"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_diff",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def git_diff(file: str = None, staged: bool = False) -> str:
  """Get git diff output

  Args:
      file: Optional specific file to diff
      staged: Whether to show staged changes (--cached)

  Returns:
      Diff output as string, or error message

  Use when:
  - Reviewing changes before commit
  - Understanding modifications
  - Generating patch files
  - Validating expected changes

  Output format:
  - Unified diff format
  - Shows added/removed lines
  - Includes file headers
  - Empty string if no differences

  Common patterns:
  - git_diff(): All unstaged changes
  - git_diff(staged=True): All staged changes
  - git_diff("file.py"): Specific file changes
  - git_diff("file.py", staged=True): Staged changes for file

  Note: File must be tracked by git
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
