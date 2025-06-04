"""Claude Code MCP Tools

Minimal tool set for Claude Code integration, providing session management
and task execution capabilities through the Model Context Protocol.
"""

from typing import Dict, List
import logging

from ..server import mcp
from ..core import Session, Task, GitOperations

logger = logging.getLogger(__name__)


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,  # Creates new session
    "openWorldHint": True,  # May invoke external Claude Code
  }
)
def start_session(goal: str) -> Dict:
  """Start a new coding session with specified goal

  Creates a session to track related development tasks working
  toward a specific engineering objective.

  Args:
      goal: Engineering objective for the session

  Returns:
      Session details including ID and starting Git state

  Use when:
  - Beginning focused development work
  - Starting feature implementation
  - Initiating refactoring efforts
  - Creating experimental branches

  Session properties:
  - Persistent across multiple tasks
  - Tracks cumulative Git changes
  - Maintains context between operations
  - Enables incremental progress

  Return format:
  {"session_id": "uuid", "goal": "...", "start_commit": "abc12345", "created_at": "ISO 8601"}

  Example: start_session("Implement user authentication with JWT tokens")
  """
  session = Session(goal)
  session.save()

  logger.info(f"Started session {session.id}: {goal}")

  return {
    "session_id": session.id,
    "goal": goal,
    "start_commit": session.start_commit[:8],
    "created_at": session.created_at.isoformat(),
  }


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # May modify files
    "idempotentHint": False,
    "openWorldHint": True,  # Executes Claude Code
  }
)
def run_task(session_id: str, intent: str) -> Dict:
  """Execute a development task within a session

  Runs Claude Code with the specified intent, tracking Git state
  changes and committing successful modifications.

  Args:
      session_id: ID of the active session
      intent: Natural language description of the task

  Returns:
      Task execution results including success status and Git commits

  Use when:
  - Implementing specific features
  - Making targeted code changes
  - Running development operations
  - Building toward session goal

  Task execution:
  - Runs Claude Code with natural language intent
  - Automatically tracks file modifications
  - Commits successful changes
  - Preserves session context

  Intent guidelines:
  - Be specific about desired outcome
  - Reference files or components
  - Include constraints or requirements
  - Build on previous task results

  Return format:
  {
    "task_id": "uuid",
    "success": true/false,
    "intent": "original intent",
    "before_commit": "abc12345",
    "after_commit": "def67890" or null,
    "changes_made": true/false
  }

  Example: run_task(session_id, "Add input validation to the login form")
  """
  # Load session
  try:
    session = Session.load(session_id)
  except FileNotFoundError:
    return {"error": f"Session {session_id} not found"}

  # Create and execute task
  task = Task(intent, session_id)
  success = task.execute()

  # Save task to session
  session.add_task(task)

  logger.info(f"Task {task.id} {'succeeded' if success else 'failed'}")

  return {
    "task_id": task.id,
    "success": success,
    "intent": intent,
    "before_commit": task.before_commit[:8],
    "after_commit": task.after_commit[:8] if task.after_commit else None,
    "changes_made": task.after_commit != task.before_commit,
  }


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
def list_sessions() -> List[Dict]:
  """List all coding sessions

  Returns summary information for all sessions including goals,
  creation times, and task counts.

  Returns:
      List of session summaries sorted by recency

  Session summary includes:
  - id: Session identifier
  - goal: Engineering objective
  - created_at: Creation timestamp
  - task_count: Number of tasks executed
  - age: Human-readable time since creation

  Use when:
  - Reviewing development history
  - Finding previous work
  - Understanding project progress
  - Resuming interrupted sessions

  Ordering:
  - Most recent sessions first
  - Age displayed as "X days/hours/minutes ago"
  """
  sessions = Session.list_all()

  # Add relative time information
  from datetime import datetime

  now = datetime.now()

  for session in sessions:
    created = session["created_at"]
    delta = now - created

    if delta.days > 0:
      session["age"] = f"{delta.days} days ago"
    elif delta.seconds > 3600:
      session["age"] = f"{delta.seconds // 3600} hours ago"
    else:
      session["age"] = f"{delta.seconds // 60} minutes ago"

  return sessions


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
def session_info(session_id: str) -> Dict:
  """Get detailed session information

  Retrieves complete session history including all tasks and
  their execution results.

  Args:
      session_id: ID of the session to inspect

  Returns:
      Full session details with task history

  Information includes:
  - Session metadata (id, goal, timestamps)
  - Task statistics (count, success rate)
  - Detailed task history with:
    - Intent descriptions
    - Success/failure status
    - Git commit transitions
    - Execution timestamps

  Use when:
  - Reviewing session progress
  - Understanding task outcomes
  - Debugging failed operations
  - Planning next steps

  Task history format:
  Each task shows:
  - Natural language intent
  - Execution result
  - Before/after commit hashes
  - Timestamp of execution

  Error: Returns {"error": "message"} if session not found
  """
  try:
    session = Session.load(session_id)
  except FileNotFoundError:
    return {"error": f"Session {session_id} not found"}

  # Calculate session statistics
  successful_tasks = sum(1 for task in session.tasks if task.get("success"))
  total_tasks = len(session.tasks)

  return {
    "id": session.id,
    "goal": session.goal,
    "created_at": session.created_at.isoformat(),
    "start_commit": session.start_commit[:8],
    "task_count": total_tasks,
    "success_rate": f"{(successful_tasks / total_tasks * 100):.0f}%" if total_tasks > 0 else "N/A",
    "tasks": [
      {
        "intent": task["intent"],
        "success": task["success"],
        "created_at": task["created_at"].isoformat(),
        "commits": {
          "before": task["before_commit"][:8],
          "after": task["after_commit"][:8] if task["after_commit"] else None,
        },
      }
      for task in session.tasks
    ],
  }


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
def git_status() -> Dict:
  """Get current Git repository status

  Returns current branch, commit, and working directory state
  optimized for Claude Code session context.

  Returns:
      Git status information

  Provides:
  - branch: Current Git branch
  - commit: Short commit hash (8 chars)
  - clean: Whether working directory is clean
  - changes: Breakdown of uncommitted changes

  Change categories:
  - modified: Changed tracked files
  - added: New or untracked files
  - deleted: Removed files
  - total: Sum of all changes

  Use when:
  - Checking repository state before session
  - Verifying clean working directory
  - Understanding pending changes
  - Confirming task results

  Note: This is a simplified status focused on Claude Code workflows.
  For detailed Git information, use the git_status tool from git module.
  """
  try:
    # Get basic status
    branch = GitOperations.get_current_branch()
    commit = GitOperations.get_current_commit()
    is_clean = GitOperations.is_clean()

    # Get change summary if not clean
    changes = {}
    if not is_clean:
      # Get uncommitted changes
      status_output = GitOperations.get_output(["status", "--porcelain"])
      modified = 0
      added = 0
      deleted = 0

      for line in status_output.splitlines():
        if line.startswith("M"):
          modified += 1
        elif line.startswith("A") or line.startswith("??"):
          added += 1
        elif line.startswith("D"):
          deleted += 1

      changes = {
        "modified": modified,
        "added": added,
        "deleted": deleted,
        "total": modified + added + deleted,
      }

    return {
      "branch": branch,
      "commit": commit[:8],
      "clean": is_clean,
      "changes": changes if changes else None,
    }

  except Exception as e:
    return {"error": f"Failed to get Git status: {str(e)}"}
