"""Claude Code MCP Tools

Minimal tool set for Claude Code integration, providing session management
and task execution capabilities through the Model Context Protocol.
"""

from typing import Dict, List
import logging

from ..server import mcp
from ..core import Session, GitOperations, document_tool
from .claude_code_enhanced import run_task_enhanced, session_info_enhanced, list_sessions_enhanced

logger = logging.getLogger(__name__)

TOOL_PREFIX = "session"


@document_tool(
  name="session_start",
  purpose="Initialize a Claude Code session for goal-oriented development",
  category="Claude Code Sessions",
  operational_model="""
  Creates a persistent session container that tracks progress toward an engineering
  goal. Session maintains context across multiple Claude Code invocations,
  accumulating knowledge and tracking Git state changes.
  """,
  usage_scenarios=[
    {
      "condition": "Beginning feature implementation",
      "rationale": "Session provides continuity across multiple development steps",
    },
    {"condition": "Starting refactoring effort", "rationale": "Tracks cumulative changes toward architectural goal"},
    {"condition": "Exploring solution alternatives", "rationale": "Sessions can be forked to try different approaches"},
  ],
  examples=[
    {
      "title": "Start feature session",
      "code": 'session = session_start("Implement user authentication with JWT")',
      "explanation": "Begin focused work on auth feature",
      "complexity": 1,
    },
    {
      "title": "Start refactoring session",
      "code": """session = session_start("Migrate database layer to async")
print(f"Session {session['session_id']} started from {session['start_commit']}")""",
      "explanation": "Track starting point for major refactor",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Git repository error",
      "cause": "Not in git repository or git unavailable",
      "diagnosis": "Check git_status first",
      "recovery": "Initialize git or fix git configuration",
      "state_impact": "Session not created",
    }
  ],
  performance={
    "time_complexity": "O(1) - metadata creation",
    "memory_usage": "Minimal - session metadata only",
    "concurrency": "Safe - each session independent",
  },
  see_also={
    "session_run_task": "Execute tasks within session",
    "session_list": "View all sessions",
    "git_status": "Check repository state first",
  },
  composition=["project_status → session_start → session_run_task", "session_start → session_run_task → git_commit"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_start",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,  # Creates new session
    "openWorldHint": True,  # May invoke external Claude Code
  },
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


@document_tool(
  name="session_run_task",
  purpose="Execute Claude Code with natural language intent within a session context",
  category="Claude Code Sessions",
  operational_model="""
  Invokes Claude Code with the specified intent, inheriting session context
  and knowledge. Tracks file modifications and commits successful changes.
  Task results contribute back to session's accumulated understanding.
  """,
  usage_scenarios=[
    {
      "condition": "Implementing specific feature components",
      "rationale": "Claude Code handles complex implementation details",
    },
    {
      "condition": "Making incremental progress toward goal",
      "rationale": "Each task builds on previous session knowledge",
    },
    {
      "condition": "Delegating repetitive code changes",
      "rationale": "Natural language intent more efficient than manual edits",
    },
  ],
  anti_patterns=[
    {
      "condition": "Vague or ambiguous intents",
      "reason": "Claude Code needs clear direction",
      "alternative": "Be specific about files, methods, and outcomes",
    },
    {
      "condition": "Multiple unrelated changes",
      "reason": "Tasks should be atomic",
      "alternative": "Split into separate focused tasks",
    },
  ],
  examples=[
    {
      "title": "Add validation",
      "code": 'result = session_run_task(session_id, "Add email validation to user registration")',
      "explanation": "Specific implementation task",
      "complexity": 1,
    },
    {
      "title": "Refactor with constraints",
      "code": """result = session_run_task(session_id,
    "Extract database queries into repository pattern, maintain existing API")""",
      "explanation": "Complex refactoring with requirements",
      "complexity": 2,
    },
    {
      "title": "Progressive implementation",
      "code": """# First task
session_run_task(sid, "Create User model with basic fields")
# Building on previous
session_run_task(sid, "Add password hashing to User model")
# Further refinement
session_run_task(sid, "Add email verification to User model")""",
      "explanation": "Incremental feature building",
      "complexity": 3,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Session not found",
      "cause": "Invalid session ID",
      "diagnosis": "Use session_list to find valid sessions",
      "recovery": "Start new session or use correct ID",
      "state_impact": "No task executed",
    },
    {
      "error_type": "Claude Code failure",
      "cause": "Implementation error or unclear intent",
      "diagnosis": "Review task intent and error output",
      "recovery": "Refine intent or fix blocking issues",
      "state_impact": "No commits made, session continues",
    },
  ],
  performance={
    "time_complexity": "Varies with task complexity",
    "memory_usage": "Depends on Claude Code operations",
    "concurrency": "Serial within session",
  },
  see_also={"session_info": "Review task history", "git_diff": "See changes made by task"},
  composition=["session_start → session_run_task → git_status", "session_run_task → git_diff → session_run_task"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_run_task",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # May modify files
    "idempotentHint": False,
    "openWorldHint": True,  # Executes Claude Code
  },
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
  # Use the enhanced implementation
  return run_task_enhanced(session_id, intent)


@document_tool(
  name="session_list",
  purpose="Display all Claude Code sessions with summary information",
  category="Claude Code Sessions",
  operational_model="""
  Retrieves metadata for all sessions, sorted by recency. Includes goal,
  creation time, task count, and human-readable age. Enables session discovery
  and progress tracking.
  """,
  usage_scenarios=[
    {"condition": "Resuming interrupted work", "rationale": "Find relevant session to continue"},
    {"condition": "Reviewing development history", "rationale": "Understand what work has been done"},
    {"condition": "Managing multiple features", "rationale": "Track progress across different goals"},
  ],
  examples=[
    {
      "title": "List all sessions",
      "code": "sessions = session_list()",
      "explanation": "Get overview of all work",
      "complexity": 1,
    },
    {
      "title": "Find recent sessions",
      "code": """sessions = session_list()
recent = [s for s in sessions if "hours ago" in s["age"] or "minutes ago" in s["age"]]""",
      "explanation": "Filter to today's work",
      "complexity": 2,
    },
  ],
  performance={
    "time_complexity": "O(n) with session count",
    "memory_usage": "Proportional to session count",
    "concurrency": "Thread-safe",
  },
  see_also={"session_info": "Get detailed session information", "session_start": "Create new session"},
  composition=["session_list → session_info → session_run_task"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_list",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
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
  # Use the enhanced implementation
  return list_sessions_enhanced()


@document_tool(
  name="session_info",
  purpose="Retrieve comprehensive details about a specific Claude Code session",
  category="Claude Code Sessions",
  operational_model="""
  Loads full session history including all tasks, their intents, execution results,
  and Git state transitions. Calculates success rates and provides chronological
  task timeline.
  """,
  usage_scenarios=[
    {"condition": "Reviewing session progress", "rationale": "Understand completed work and remaining tasks"},
    {"condition": "Debugging failed tasks", "rationale": "Examine failure patterns and error contexts"},
    {"condition": "Planning next steps", "rationale": "Base decisions on session history"},
  ],
  examples=[
    {
      "title": "Review session details",
      "code": "info = session_info(session_id)",
      "explanation": "Get full session history",
      "complexity": 1,
    },
    {
      "title": "Analyze success rate",
      "code": """info = session_info(session_id)
print(f"Success rate: {info['success_rate']}")
failed = [t for t in info['tasks'] if not t['success']]""",
      "explanation": "Identify problematic tasks",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Session not found",
      "cause": "Invalid session ID",
      "diagnosis": "Session may have been deleted",
      "recovery": "Use session_list to find valid sessions",
      "state_impact": "Returns error dict",
    }
  ],
  performance={
    "time_complexity": "O(n) with task count",
    "memory_usage": "Full session history loaded",
    "concurrency": "Thread-safe reads",
  },
  see_also={"session_list": "Find session IDs", "git_log": "See commits from tasks"},
  composition=["session_list → session_info → session_run_task"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_info",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
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
  # Use the enhanced implementation
  return session_info_enhanced(session_id)


@document_tool(
  name="session_git_status",
  purpose="Quick Git status check optimized for Claude Code workflows",
  category="Claude Code Sessions",
  operational_model="""
  Provides simplified Git status focused on session-relevant information:
  branch, commit, cleanliness, and change counts. Streamlined alternative
  to full git_status for session contexts.
  """,
  usage_scenarios=[
    {"condition": "Before starting a session", "rationale": "Ensure clean starting state"},
    {"condition": "After task execution", "rationale": "Verify expected changes"},
    {"condition": "Quick repository check", "rationale": "Lightweight status for session tools"},
  ],
  examples=[
    {
      "title": "Check if clean",
      "code": """status = session_git_status()
if status["clean"]:
    session_start("New feature")""",
      "explanation": "Verify clean state before session",
      "complexity": 1,
    },
    {
      "title": "Count changes",
      "code": """status = session_git_status()
if status["changes"]:
    print(f"Total changes: {status['changes']['total']}")""",
      "explanation": "Quick change summary",
      "complexity": 2,
    },
  ],
  performance={
    "time_complexity": "O(n) with file count",
    "memory_usage": "Minimal - counts only",
    "concurrency": "Thread-safe",
  },
  see_also={"git_status": "Full Git status details", "session_start": "Begin new session"},
  composition=["session_git_status → session_start"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_git_status",
  annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
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
