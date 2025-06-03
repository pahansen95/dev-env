"""Development task execution for Claude Code integration"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
from enum import Enum
import importlib.util
import logging

from .session import CodingSession
from .executor import ClaudeCodeExecutor, ClaudeCodeOutput
from .git_tracker import GitStateTracker
from .context import SessionContext, VerificationResult

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
  """Bounded transformation operation executed through Claude Code"""

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
    self.base_path.mkdir(parents=True, exist_ok=True)

    # Save initial config
    self._save_config()
    logger.info(f"Initialized task {self.id}: {self.intent[:50]}...")

  def _save_config(self):
    """Persist task configuration"""
    config_path = self.base_path / "config.py"

    config_content = f'''# Development task configuration
from datetime import datetime
from models.task import TaskType, TaskStatus

TASK_CONFIG = {{
    "id": "{self.id}",
    "session_id": {repr(self.session_id)},
    "intent": {repr(self.intent)},
    "scope": {repr(self.scope)},
    "task_type": TaskType.{self.task_type.name},
    "status": TaskStatus.{self.status.name},
    "created_at": datetime.fromisoformat("{self.created_at.isoformat()}"),
    "updated_at": datetime.fromisoformat("{self.updated_at.isoformat()}"),
    "verification_passed": {repr(self.verification_passed)},
}}
'''

    with open(config_path, "w") as f:
      f.write(config_content)

  def _load_config(self):
    """Load task configuration"""
    config_path = self.base_path / "config.py"

    spec = importlib.util.spec_from_file_location("config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config = module.TASK_CONFIG
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

    if any(word in intent_lower for word in ["review", "check", "analyze"]):
      return TaskType.REVIEW
    elif any(word in intent_lower for word in ["test", "testing", "coverage"]):
      return TaskType.TEST
    elif any(word in intent_lower for word in ["refactor", "restructure", "reorganize"]):
      return TaskType.REFACTOR
    elif any(word in intent_lower for word in ["document", "docs", "comment"]):
      return TaskType.DOCUMENT
    elif any(word in intent_lower for word in ["debug", "fix", "resolve", "error"]):
      return TaskType.DEBUG
    else:
      return TaskType.IMPLEMENT

  def execute(self, context: SessionContext) -> "DevTask":
    """Execute task with Claude Code"""
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
      self.result = ClaudeCodeOutput("", str(e), -1)

    finally:
      # Restore stashed changes if any
      if stash_ref:
        try:
          GitStateTracker.run_git_command(["stash", "pop"])
          logger.info("Restored stashed changes")
        except Exception as e:
          logger.warning(f"Failed to restore stash: {e}")

      # Save final state
      self.updated_at = datetime.now()
      self._save_config()

    return self

  def _verify_changes(self) -> bool:
    """Verify task execution results"""
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

    result_path = self.base_path / "result.py"

    result_content = f'''# Task execution result
from datetime import datetime

RESULT = {{
    "stdout": """{self.result.stdout}""",
    "stderr": """{self.result.stderr}""",
    "return_code": {self.result.return_code},
    "timestamp": datetime.fromisoformat("{self.result.timestamp.isoformat()}"),
    "files_modified": {repr(self.result.files_modified)},
    "files_created": {repr(self.result.files_created)},
    "tests_run": {self.result.tests_run},
    "tests_passed": {self.result.tests_passed},
}}

GIT_STATE = {{
    "before": {repr(self.git_state_before)},
    "after": {repr(self.git_state_after)},
}}
'''

    with open(result_path, "w") as f:
      f.write(result_content)

  def get_diff(self) -> str:
    """Get diff of changes made by this task"""
    if not self.git_state_before or not self.git_state_after:
      return "No state information available"

    return GitStateTracker.get_file_diff(
      None,  # All files
      self.git_state_before["commit"],
    )

  def rollback(self) -> bool:
    """Rollback changes made by this task"""
    if self.status != TaskStatus.COMPLETED:
      logger.warning(f"Cannot rollback task {self.id} with status {self.status}")
      return False

    try:
      # Reset to state before task
      GitStateTracker.run_git_command(["reset", "--hard", self.git_state_before["commit"]])

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
    """Create new task"""
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
