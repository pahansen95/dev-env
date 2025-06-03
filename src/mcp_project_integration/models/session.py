"""Coding session management for Claude Code integration"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum
import importlib.util
import logging

from .context import SessionContext
from .git_tracker import GitStateTracker

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
  """Session lifecycle states"""

  ACTIVE = "active"
  COMPLETED = "completed"
  ARCHIVED = "archived"
  FAILED = "failed"


class CodingSession:
  """Manages a stateful development context toward an engineering goal"""

  def __init__(self, session_id: Optional[str] = None, goal: Optional[str] = None, base_path: Optional[Path] = None):
    self.id = session_id or str(uuid.uuid4())
    self.goal = goal
    self.base_path = base_path or Path(".cache/.agent/sessions") / self.id

    # Initialize or load session
    if self.base_path.exists():
      self._load_config()
    else:
      self._initialize_new_session()

    # Load or create context
    self.context = SessionContext.load(self.base_path / "context.py", self.id)

  def _initialize_new_session(self):
    """Set up new session"""
    self.status = SessionStatus.ACTIVE
    self.created_at = datetime.now()
    self.updated_at = self.created_at
    self.git_branch = GitStateTracker.current_branch()
    self.git_start = GitStateTracker.current_commit()
    self.checkpoint_count = 0

    # Create directory structure
    self.base_path.mkdir(parents=True, exist_ok=True)
    (self.base_path / "tasks").mkdir(exist_ok=True)
    (self.base_path / "checkpoints").mkdir(exist_ok=True)
    (self.base_path / "claude_history").mkdir(exist_ok=True)

    # Save initial config
    self._save_config()
    logger.info(f"Initialized new session {self.id} with goal: {self.goal}")

  def _save_config(self):
    """Persist session configuration to Python file"""
    config_path = self.base_path / "config.py"

    config_content = f'''# Coding session configuration
from datetime import datetime
from models.session import SessionStatus

SESSION_CONFIG = {{
    "id": "{self.id}",
    "goal": {repr(self.goal)},
    "status": SessionStatus.{self.status.name},
    "created_at": datetime.fromisoformat("{self.created_at.isoformat()}"),
    "updated_at": datetime.fromisoformat("{self.updated_at.isoformat()}"),
    "git_branch": "{self.git_branch}",
    "git_start": "{self.git_start}",
    "checkpoint_count": {self.checkpoint_count},
}}
'''

    with open(config_path, "w") as f:
      f.write(config_content)

  def _load_config(self):
    """Load session configuration from Python file"""
    config_path = self.base_path / "config.py"

    # Load module dynamically
    spec = importlib.util.spec_from_file_location("config", config_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config = module.SESSION_CONFIG
    self.goal = config["goal"]
    self.status = config["status"]
    self.created_at = config["created_at"]
    self.updated_at = config["updated_at"]
    self.git_branch = config["git_branch"]
    self.git_start = config["git_start"]
    self.checkpoint_count = config["checkpoint_count"]

  def link_task(self, task_id: str):
    """Create symlink from task to session"""
    task_link = self.base_path / "tasks" / task_id
    task_target = Path("../../tasks") / task_id

    if not task_link.exists():
      task_link.symlink_to(task_target)
      logger.info(f"Linked task {task_id} to session {self.id}")

  def get_file_changes(self) -> Dict[str, List[str]]:
    """Get all file changes since session start"""
    return GitStateTracker.get_changes_since(self.git_start)

  def checkpoint(self, message: Optional[str] = None) -> str:
    """Create session checkpoint"""
    self.checkpoint_count += 1
    checkpoint_message = message or f"Session {self.id} checkpoint {self.checkpoint_count}"

    # Save current context
    self.context.save(self.base_path / "context.py")

    # Create Git commit with metadata
    metadata = {
      "session_id": self.id,
      "checkpoint": self.checkpoint_count,
      "goal": self.goal,
    }

    commit_sha = GitStateTracker.commit(checkpoint_message, metadata)

    # Save checkpoint reference
    checkpoint_path = self.base_path / "checkpoints" / f"{self.checkpoint_count:03d}.py"
    with open(checkpoint_path, "w") as f:
      f.write(f"# Checkpoint {self.checkpoint_count}\n")
      f.write("CHECKPOINT = {\n")
      f.write(f'    "number": {self.checkpoint_count},\n')
      f.write(f'    "commit": "{commit_sha}",\n')
      f.write(f'    "timestamp": "{datetime.now().isoformat()}",\n')
      f.write(f'    "message": {repr(message)},\n')
      f.write("}\n")

    self.updated_at = datetime.now()
    self._save_config()

    logger.info(f"Created checkpoint {self.checkpoint_count} at {commit_sha}")
    return commit_sha

  def complete(self, verification_passed: bool = True) -> bool:
    """Mark session as completed"""
    if verification_passed:
      self.status = SessionStatus.COMPLETED
      logger.info(f"Session {self.id} completed successfully")
    else:
      self.status = SessionStatus.FAILED
      logger.warning(f"Session {self.id} failed verification")

    self.updated_at = datetime.now()
    self._save_config()
    self.context.save(self.base_path / "context.py")

    # Create final checkpoint
    self.checkpoint(f"Session {self.id} {'completed' if verification_passed else 'failed'}")

    return verification_passed

  def archive(self):
    """Archive completed session"""
    if self.status not in [SessionStatus.COMPLETED, SessionStatus.FAILED]:
      logger.warning(f"Cannot archive active session {self.id}")
      return

    self.status = SessionStatus.ARCHIVED
    self.updated_at = datetime.now()
    self._save_config()

    logger.info(f"Archived session {self.id}")

  def save_claude_history(self, conversation: str, timestamp: Optional[datetime] = None):
    """Save Claude conversation history"""
    ts = timestamp or datetime.now()
    history_file = self.base_path / "claude_history" / f"{ts.strftime('%Y%m%d_%H%M%S')}.py"

    with open(history_file, "w") as f:
      f.write("# Claude conversation history\n")
      f.write(f'TIMESTAMP = "{ts.isoformat()}"\n')
      f.write(f'CONVERSATION = """\n{conversation}\n"""\n')

  def get_linked_tasks(self) -> List[str]:
    """Get list of task IDs linked to this session"""
    tasks_dir = self.base_path / "tasks"
    if not tasks_dir.exists():
      return []

    return sorted([task.name for task in tasks_dir.iterdir() if task.is_symlink()])

  @classmethod
  def create(cls, goal: str) -> "CodingSession":
    """Create new coding session"""
    session = cls(goal=goal)
    return session

  @classmethod
  def load(cls, session_id: str) -> "CodingSession":
    """Load existing session"""
    base_path = Path(".cache/.agent/sessions") / session_id
    if not base_path.exists():
      raise FileNotFoundError(f"Session {session_id} not found")

    return cls(session_id=session_id, base_path=base_path)

  @classmethod
  def list_sessions(cls) -> List[Dict[str, any]]:
    """List all available sessions"""
    sessions_dir = Path(".cache/.agent/sessions")
    if not sessions_dir.exists():
      return []

    sessions = []
    for session_path in sessions_dir.iterdir():
      if session_path.is_dir() and (session_path / "config.py").exists():
        try:
          session = cls.load(session_path.name)
          sessions.append(
            {
              "id": session.id,
              "goal": session.goal,
              "status": session.status.value,
              "created_at": session.created_at,
              "updated_at": session.updated_at,
              "task_count": len(session.get_linked_tasks()),
            }
          )
        except Exception as e:
          logger.error(f"Failed to load session {session_path.name}: {e}")

    return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)
