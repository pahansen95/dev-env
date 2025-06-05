"""Claude Code MCP Tools

Minimal tool set for Claude Code integration, providing session management
and task execution capabilities through the Model Context Protocol.
"""

from typing import Dict, List
import logging

from ..server import mcp
from ..core import Session, Task, GitOperations, document_tool


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
  # Load session
  try:
    session = Session.load(session_id)
  except FileNotFoundError:
    return {"error": f"Session {session_id} not found"}
  except Exception as e:
    return {"error": f"Failed to load session: {type(e).__name__}: {str(e)}"}

  # Create and execute task
  task = Task(intent, session_id)
  success = task.execute()

  # Save task to session
  session.add_task(task)

  logger.info(f"Task {task.id} {'succeeded' if success else 'failed'}")

  # Build comprehensive response
  response = {
    "task_id": task.id,
    "success": success,
    "intent": intent,
    "before_commit": task.before_commit[:8],
    "after_commit": task.after_commit[:8] if task.after_commit else None,
    "changes_made": task.after_commit != task.before_commit,
  }

  # Add execution metadata
  if task.execution_metadata:
    response["execution"] = {
      "time_seconds": task.execution_metadata.get("execution_time_seconds"),
      "timeout": task.execution_metadata.get("timeout", False),
      "error": task.execution_metadata.get("execution_error"),
    }

    # Add git change information
    if "post_execution_changes" in task.execution_metadata:
      changes = task.execution_metadata["post_execution_changes"]
      response["changes"] = {
        "summary": changes.get("summary", ""),
        "total_files": changes.get("total", 0),
        "staged": len(changes.get("staged", [])),
        "modified": len(changes.get("modified", [])),
        "untracked": len(changes.get("untracked", [])),
      }

  # Add Claude Code output information
  if task.parsed_output:
    claude_info = {
      "session_id": task.parsed_output.session_id,
      "cost_usd": task.parsed_output.total_cost,
      "duration_ms": task.parsed_output.duration_ms,
      "api_turns": task.parsed_output.num_turns,
      "tools_available": len(task.parsed_output.tools_available),
    }

    # Add tool usage summary
    tool_usage = task.parsed_output.get_tool_usage()
    if tool_usage:
      tool_counts = {}
      for tool in tool_usage:
        tool_name = tool["name"]
        tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

      claude_info["tools_used"] = tool_counts
      claude_info["total_tool_calls"] = len(tool_usage)

    # Add result or error
    if task.parsed_output.final_result:
      claude_info["result_preview"] = (
        task.parsed_output.final_result[:200] + "..."
        if len(task.parsed_output.final_result) > 200
        else task.parsed_output.final_result
      )
    if task.parsed_output.error:
      claude_info["error"] = task.parsed_output.error

    response["claude_code"] = claude_info

    # Add conversation flow summary
    flow = task.parsed_output.get_conversation_flow()
    if flow:
      response["conversation"] = {
        "steps": len(flow),
        "flow_summary": [
          f"{step['role']}: {step['type']}" + (f" - {step['tool']}" if step.get("tool") else "") for step in flow[:5]
        ],
      }
      if len(flow) > 5:
        response["conversation"]["flow_summary"].append(f"... and {len(flow) - 5} more steps")

  return response


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
  sessions = Session.list_all()

  # Add enhanced information
  from datetime import datetime

  now = datetime.now()

  enhanced_sessions = []

  for session_data in sessions:
    # Calculate age
    created = session_data["created_at"]
    delta = now - created

    if delta.days > 0:
      age = f"{delta.days} days ago"
    elif delta.seconds > 3600:
      age = f"{delta.seconds // 3600} hours ago"
    else:
      age = f"{delta.seconds // 60} minutes ago"

    enhanced_session = {
      "id": session_data["id"],
      "goal": session_data["goal"],
      "created_at": session_data["created_at"].isoformat(),
      "task_count": session_data["task_count"],
      "age": age,
    }

    # Try to load session for additional stats (optional enhancement)
    try:
      # Quick check if session file has cost information
      session = Session.load(session_data["id"])
      total_cost = 0.0
      successful = 0

      for task in session.tasks:
        if task.get("success"):
          successful += 1

        # Check for cost in execution metadata
        exec_meta = task.get("execution_metadata", {})
        if "cost_usd" in exec_meta and exec_meta["cost_usd"] is not None:
          total_cost += exec_meta["cost_usd"]

      if session.tasks:
        enhanced_session["success_rate"] = f"{(successful / len(session.tasks) * 100):.0f}%"

      if total_cost > 0:
        enhanced_session["total_cost_usd"] = round(total_cost, 6)

    except Exception as e:
      # If we can't load the session, just skip the extra stats
      logger.debug(f"Could not load session {session_data['id']} for stats: {e}")

    enhanced_sessions.append(enhanced_session)

  return enhanced_sessions


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
  try:
    session = Session.load(session_id)
  except FileNotFoundError:
    return {"error": f"Session {session_id} not found"}
  except Exception as e:
    return {"error": f"Failed to load session: {type(e).__name__}: {str(e)}"}

  # Calculate session statistics
  successful_tasks = 0
  total_cost = 0.0
  total_api_duration = 0
  total_tool_calls = 0
  tool_usage_summary = {}

  enhanced_tasks = []

  for task_data in session.tasks:
    if task_data.get("success"):
      successful_tasks += 1

    # Build enhanced task info
    task_info = {
      "intent": task_data["intent"],
      "success": task_data["success"],
      "created_at": task_data["created_at"].isoformat(),
      "commits": {
        "before": task_data["before_commit"][:8],
        "after": task_data["after_commit"][:8] if task_data["after_commit"] else None,
      },
    }

    # Add execution metadata if available
    exec_meta = task_data.get("execution_metadata", {})
    if exec_meta:
      task_info["execution_time"] = exec_meta.get("execution_time_seconds")

      # Add Claude Code info if available
      if "cost_usd" in exec_meta and exec_meta["cost_usd"] is not None:
        total_cost += exec_meta["cost_usd"]
        task_info["cost_usd"] = exec_meta["cost_usd"]

      if "duration_ms" in exec_meta and exec_meta["duration_ms"] is not None:
        total_api_duration += exec_meta["duration_ms"]
        task_info["api_duration_ms"] = exec_meta["duration_ms"]

      # Aggregate tool usage
      if "tool_usage" in exec_meta:
        for tool in exec_meta["tool_usage"]:
          tool_name = tool.get("name", "unknown")
          tool_usage_summary[tool_name] = tool_usage_summary.get(tool_name, 0) + 1
          total_tool_calls += 1

      # Add change summary
      if "post_execution_changes" in exec_meta:
        changes = exec_meta["post_execution_changes"]
        task_info["changes"] = changes.get("summary", "no changes")

    # Add Claude output summary if available
    claude_output = task_data.get("claude_output", {})
    if claude_output:
      task_info["claude"] = {
        "session_id": claude_output.get("session_id"),
        "turns": claude_output.get("num_turns"),
        "tools": claude_output.get("tool_count", 0),
      }

    enhanced_tasks.append(task_info)

  total_tasks = len(session.tasks)

  return {
    "id": session.id,
    "goal": session.goal,
    "created_at": session.created_at.isoformat(),
    "start_commit": session.start_commit[:8],
    "task_count": total_tasks,
    "success_rate": f"{(successful_tasks / total_tasks * 100):.0f}%" if total_tasks > 0 else "N/A",
    "statistics": {
      "total_cost_usd": round(total_cost, 6) if total_cost > 0 else None,
      "total_api_duration_ms": total_api_duration if total_api_duration > 0 else None,
      "total_tool_calls": total_tool_calls if total_tool_calls > 0 else None,
      "tool_usage": tool_usage_summary if tool_usage_summary else None,
    },
    "tasks": enhanced_tasks,
  }


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
