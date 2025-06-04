"""Minimal session management for Claude Code integration

Provides lightweight session and task tracking with Git integration
for managing Claude Code development workflows.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

from .serialization import PythonConfigSerializer
from .utils import GitOperations, SubprocessRunner

logger = logging.getLogger(__name__)


class Task:
  """Represents a single Claude Code execution

  Tasks capture the intent, Git state changes, and execution results
  for bounded development operations within a session.
  """

  def __init__(self, intent: str, session_id: str):
    self.id = str(uuid.uuid4())
    self.session_id = session_id
    self.intent = intent
    self.created_at = datetime.now()
    self.before_commit = GitOperations.get_current_commit()
    self.after_commit: Optional[str] = None
    self.success: Optional[bool] = None
    self.output: Optional[str] = None

  def execute(self) -> bool:
    """Execute Claude Code with the task intent

    Manages Git state, runs Claude Code subprocess, and commits
    successful changes. Returns execution success status.
    """
    # Ensure clean working directory
    stash_ref = None
    if not GitOperations.is_clean():
      logger.info(f"Stashing changes for task {self.id}")
      stash_ref = GitOperations.stash(f"Task {self.id}")

    try:
      # Execute Claude Code
      logger.info(f"Executing task: {self.intent[:100]}")
      result = SubprocessRunner.run(
        command=["claude-code", "--non-interactive"], env={"CLAUDE_CODE_INTENT": self.intent}, timeout=300, check=False
      )

      self.output = result.stdout
      self.success = result.success

      # Commit changes if successful
      if self.success and not GitOperations.is_clean():
        GitOperations.stage_all()
        self.after_commit = GitOperations.commit(
          f"Task: {self.intent[:50]}", body=f"task_id: {self.id}\nsession_id: {self.session_id}"
        )
        logger.info(f"Committed changes: {self.after_commit[:8]}")
      else:
        self.after_commit = self.before_commit

    except Exception as e:
      logger.error(f"Task execution failed: {e}")
      self.success = False
      self.output = str(e)

    finally:
      # Restore stashed changes
      if stash_ref:
        try:
          GitOperations.run_command(["stash", "pop"])
          logger.info("Restored stashed changes")
        except Exception as e:
          logger.warning(f"Failed to restore stash: {e}")

    return self.success

  def to_dict(self) -> Dict:
    """Convert task to dictionary for persistence"""
    return {
      "id": self.id,
      "intent": self.intent,
      "created_at": self.created_at,
      "before_commit": self.before_commit,
      "after_commit": self.after_commit,
      "success": self.success,
    }


class Session:
  """Manages a development session with a specific goal

  Sessions track a series of tasks working toward an engineering
  objective, maintaining Git commit history and task results.
  """

  def __init__(self, goal: str, session_id: Optional[str] = None):
    self.id = session_id or str(uuid.uuid4())
    self.goal = goal
    self.created_at = datetime.now()
    self.start_commit = GitOperations.get_current_commit()
    self.tasks: List[Dict] = []  # Store task data, not objects

  def add_task(self, task: Task):
    """Record completed task in session history"""
    self.tasks.append(task.to_dict())
    self.save()

  def save(self):
    """Persist session to Python configuration file"""
    data = {
      "id": self.id,
      "goal": self.goal,
      "created_at": self.created_at,
      "start_commit": self.start_commit,
      "tasks": self.tasks,
    }

    # Ensure cache directory exists
    cache_dir = Path(".cache/.agent")
    cache_dir.mkdir(parents=True, exist_ok=True)

    path = cache_dir / f"{self.id}.py"
    PythonConfigSerializer.write_config(path=path, config_name="SESSION", data=data, header=f"Session: {self.goal}")
    logger.debug(f"Saved session {self.id} to {path}")

  @classmethod
  def load(cls, session_id: str) -> "Session":
    """Load session from persistent storage"""
    path = Path(".cache/.agent") / f"{session_id}.py"
    if not path.exists():
      raise FileNotFoundError(f"Session {session_id} not found")

    data = PythonConfigSerializer.read_config(path, "SESSION")

    session = cls(goal=data["goal"], session_id=data["id"])
    session.created_at = data["created_at"]
    session.start_commit = data["start_commit"]
    session.tasks = data.get("tasks", [])

    return session

  @classmethod
  def list_all(cls) -> List[Dict]:
    """List all sessions with summary information"""
    cache_dir = Path(".cache/.agent")
    if not cache_dir.exists():
      return []

    sessions = []
    for path in cache_dir.glob("*.py"):
      try:
        data = PythonConfigSerializer.read_config(path, "SESSION")
        sessions.append(
          {
            "id": data["id"],
            "goal": data["goal"],
            "created_at": data["created_at"],
            "task_count": len(data.get("tasks", [])),
          }
        )
      except Exception as e:
        logger.warning(f"Failed to load session from {path}: {e}")
        continue

    return sorted(sessions, key=lambda s: s["created_at"], reverse=True)
