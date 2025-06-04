"""Enhanced Claude Code MCP Tools with verbose output

This module contains enhanced versions of the run_task, list_sessions, and session_info
functions that leverage the new verbose output capabilities.
"""

from typing import Dict, List
import logging

from ..core import Session, Task

logger = logging.getLogger(__name__)


def run_task_enhanced(session_id: str, intent: str) -> Dict:
  """Execute a development task within a session with verbose output

  Returns comprehensive execution details including:
  - Task success/failure status
  - Git commit information
  - Claude Code execution metadata
  - Tool usage statistics
  - Cost and performance metrics
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
          f"{step['role']}: {step['type']}" + (f" - {step['tool']}" if step.get("tool") else "")
          for step in flow[:5]  # First 5 steps
        ],
      }
      if len(flow) > 5:
        response["conversation"]["flow_summary"].append(f"... and {len(flow) - 5} more steps")

  return response


def session_info_enhanced(session_id: str) -> Dict:
  """Get detailed session information with execution metadata

  Returns enhanced session details including:
  - Task execution history with Claude Code metadata
  - Cost accumulation across tasks
  - Tool usage patterns
  - Performance statistics
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


def list_sessions_enhanced() -> List[Dict]:
  """List all coding sessions with summary statistics

  Enhanced listing includes:
  - Task success rates
  - Total costs per session
  - Recent activity indicators
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
