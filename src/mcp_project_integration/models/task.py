"""Development task execution for Claude Code integration

Encapsulates bounded transformation operations executed through Claude Code,
with Git-based change tracking and verification.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from enum import Enum
import logging

from .session import CodingSession
from .executor import ClaudeCodeExecutor, ClaudeCodeOutput
from .git_tracker import GitStateTracker
from .context import SessionContext, VerificationResult
from ..core import PythonConfigSerializer
from ..core.utils import FileSystemOperations, GitOperations, SubprocessResult

logger = logging.getLogger(__name__)


class TaskType(Enum):
  """Types of development tasks"""

  REVIEW = "review"
  IMPLEMENT = "implement"
  TEST = "test"
  REFACTOR = "refactor"
  DOCUMENT = "document"
  DEBUG = "debug"


class TaskStatus(Enum):
  """Task execution states"""

  PENDING = "pending"
  RUNNING = "running"
  COMPLETED = "completed"
  FAILED = "failed"
  ROLLED_BACK = "rolled_back"


class DevTask:
  """Bounded transformation operation executed through Claude Code

  Represents a single development task within a coding session, tracking
  intent, scope, execution results, and Git state changes.
  """

  def __init__(
    self,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    intent: Optional[str] = None,
    scope: Optional[List[str]] = None,
    task_type: Optional[TaskType] = None,
    base_path: Optional[Path] = None,
  ):
    self.id = task_id or str(uuid.uuid4())
    self.session_id = session_id
    self.intent = intent
    self.scope = scope or []
    self.task_type = task_type or self._infer_task_type(intent)
    self.base_path = base_path or Path(".cache/.agent/tasks") / self.id

    # Initialize or load task
    if self.base_path.exists():
      self._load_config()
    else:
      self._initialize_new_task()

    # Execution state
    self.result: Optional[ClaudeCodeOutput] = None
    self.git_state_before: Optional[Dict] = None
    self.git_state_after: Optional[Dict] = None

  def _initialize_new_task(self):
    """Set up new task"""
    self.status = TaskStatus.PENDING
    self.created_at = datetime.now()
    self.updated_at = self.created_at
    self.verification_passed = None

    # Create directory
    FileSystemOperations.ensure_directory(self.base_path)

    # Save initial config
    self._save_config()
    logger.info(f"Initialized task {self.id}: {self.intent[:50]}...")

  def _save_config(self):
    """Persist task configuration"""
    data = {
      "id": self.id,
      "session_id": self.session_id,
      "intent": self.intent,
      "scope": self.scope,
      "task_type": self.task_type,
      "status": self.status,
      "created_at": self.created_at,
      "updated_at": self.updated_at,
      "verification_passed": self.verification_passed,
    }

    imports = {
      "datetime": "from datetime import datetime",
      "task": "from mcp_project_integration.models.task import TaskType, TaskStatus",
    }

    PythonConfigSerializer.write_config(
      path=self.base_path / "config.py",
      config_name="TASK_CONFIG",
      data=data,
      imports=imports,
      header="Development task configuration",
    )

  def _load_config(self):
    """Load task configuration"""
    config = PythonConfigSerializer.read_config(self.base_path / "config.py", "TASK_CONFIG")

    self.session_id = config["session_id"]
    self.intent = config["intent"]
    self.scope = config["scope"]
    self.task_type = config["task_type"]
    self.status = config["status"]
    self.created_at = config["created_at"]
    self.updated_at = config["updated_at"]
    self.verification_passed = config["verification_passed"]

  def _infer_task_type(self, intent: str) -> TaskType:
    """Infer task type from intent string"""
    if not intent:
      return TaskType.IMPLEMENT

    intent_lower = intent.lower()

    # Define keyword mappings
    type_keywords = {
      TaskType.REVIEW: ["review", "check", "analyze", "inspect"],
      TaskType.TEST: ["test", "testing", "coverage", "verify"],
      TaskType.REFACTOR: ["refactor", "restructure", "reorganize", "cleanup"],
      TaskType.DOCUMENT: ["document", "docs", "comment", "explain"],
      TaskType.DEBUG: ["debug", "fix", "resolve", "error", "bug"],
    }

    # Check each task type
    for task_type, keywords in type_keywords.items():
      if any(keyword in intent_lower for keyword in keywords):
        return task_type

    return TaskType.IMPLEMENT

  def execute(self, context: SessionContext) -> "DevTask":
    """Execute task with Claude Code

    Args:
        context: Session context with accumulated knowledge

    Returns:
        Self for method chaining
    """
    logger.info(f"Executing task {self.id}: {self.intent}")

    # Update status
    self.status = TaskStatus.RUNNING
    self.updated_at = datetime.now()
    self._save_config()

    # Capture pre-execution state
    self.git_state_before = GitStateTracker.capture_state()

    # Check for uncommitted changes and stash if needed
    stash_ref = None
    if not GitStateTracker.is_clean():
      logger.warning("Working directory not clean, stashing changes")
      stash_ref = GitStateTracker.stash_changes(f"Pre-task {self.id}")

    try:
      # Build context for Claude
      relevant_context = context.get_relevant_context(self.intent, self.scope)

      # Add scope information
      if self.scope:
        scope_context = f"\nScope: {', '.join(self.scope)}"
      else:
        scope_context = "\nScope: Entire project"

      full_context = relevant_context + scope_context

      # Execute via Claude Code
      executor = ClaudeCodeExecutor()
      self.result = executor.run(self.intent, full_context)

      # Capture post-execution state
      self.git_state_after = GitStateTracker.capture_state()

      # Save result
      self._save_result()

      # Verify changes
      if self.result.success:
        self.verification_passed = self._verify_changes()

        if self.verification_passed:
          self.status = TaskStatus.COMPLETED

          # Commit changes
          metadata = {
            "task_id": self.id,
            "session_id": self.session_id,
            "task_type": self.task_type.value,
          }
          GitStateTracker.commit(f"Task {self.id}: {self.intent[:50]}", metadata)

          # Update context with results
          verification = VerificationResult(
            task_id=self.id, success=True, tests_passed=self.result.tests_passed, tests_failed=0
          )
          context.add_verification(verification)

          logger.info(f"Task {self.id} completed successfully")
        else:
          self.status = TaskStatus.FAILED
          logger.warning(f"Task {self.id} failed verification")
      else:
        self.status = TaskStatus.FAILED
        logger.error(f"Task {self.id} execution failed")

    except Exception as e:
      logger.error(f"Task {self.id} failed with exception: {e}")
      self.status = TaskStatus.FAILED
      self.result = ClaudeCodeOutput(SubprocessResult("", str(e), -1, ["claude-code"]))

    finally:
      # Restore stashed changes if any
      if stash_ref:
        try:
          GitOperations.run_command(["stash", "pop"])
          logger.info("Restored stashed changes")
        except Exception as e:
          logger.warning(f"Failed to restore stash: {e}")

      # Save final state
      self.updated_at = datetime.now()
      self._save_config()

    return self

  def _verify_changes(self) -> bool:
    """Verify task execution results

    Implements task-type specific verification strategies.
    """
    if not self.result or not self.result.success:
      return False

    # Get file changes
    changes = GitStateTracker.get_uncommitted_changes()

    # Basic verification based on task type
    if self.task_type == TaskType.IMPLEMENT:
      # Check if files were created/modified as expected
      if not changes["staged"] and not changes["unstaged"]:
        logger.warning("No files changed for implementation task")
        return False

    elif self.task_type == TaskType.TEST:
      # Check if tests were added and pass
      if self.result.tests_run == 0:
        logger.warning("No tests executed")
        return False
      if self.result.tests_passed < self.result.tests_run:
        logger.warning(f"Tests failed: {self.result.tests_run - self.result.tests_passed}")
        return False

    elif self.task_type == TaskType.REVIEW:
      # Review tasks might not change files
      pass

    # Task-specific verification could be added here
    return True

  def _save_result(self):
    """Save execution result"""
    if not self.result:
      return

    result_data = self.result.to_dict()
    result_data["git_state"] = {
      "before": self.git_state_before,
      "after": self.git_state_after,
    }

    PythonConfigSerializer.write_config(
      path=self.base_path / "result.py", config_name="RESULT", data=result_data, header="Task execution result"
    )

  def get_diff(self) -> str:
    """Get diff of changes made by this task"""
    if not self.git_state_before or not self.git_state_after:
      return "No state information available"

    return GitStateTracker.get_file_diff(
      None,  # All files
      self.git_state_before["commit"],
    )

  def rollback(self) -> bool:
    """Rollback changes made by this task

    Returns:
        True if rollback succeeded
    """
    if self.status != TaskStatus.COMPLETED:
      logger.warning(f"Cannot rollback task {self.id} with status {self.status}")
      return False

    try:
      # Reset to state before task
      GitOperations.reset_hard(self.git_state_before["commit"])

      self.status = TaskStatus.ROLLED_BACK
      self.updated_at = datetime.now()
      self._save_config()

      logger.info(f"Rolled back task {self.id}")
      return True

    except Exception as e:
      logger.error(f"Failed to rollback task {self.id}: {e}")
      return False

  @classmethod
  def create(
    cls, session_id: str, intent: str, scope: Optional[List[str]] = None, task_type: Optional[TaskType] = None
  ) -> "DevTask":
    """Create new task and link to session"""
    task = cls(session_id=session_id, intent=intent, scope=scope, task_type=task_type)

    # Link to session
    session = CodingSession.load(session_id)
    session.link_task(task.id)

    return task

  @classmethod
  def load(cls, task_id: str) -> "DevTask":
    """Load existing task"""
    base_path = Path(".cache/.agent/tasks") / task_id
    if not base_path.exists():
      raise FileNotFoundError(f"Task {task_id} not found")

    return cls(task_id=task_id, base_path=base_path)
