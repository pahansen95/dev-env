"""Session and task management for Claude Code integration

# CodingSession Mental Model

A CodingSession represents a stateful development context that maintains coherent
progress toward a specific engineering goal. It serves as a persistent container
for related development activities, preserving accumulated knowledge across multiple
task executions.

## Core Properties

**Goal Definition**
- Primary objective defining the engineering outcome
- Measurable success criteria for completion
- Explicit scope boundaries for included work

**Contextual State**
- File system awareness tracking modifications
- Decision history preserving choices and rationale
- Knowledge accumulation of discovered patterns

**Execution Environment**
- Persistent binding to development container
- Configured Claude Code capabilities and permissions
- Resource limits for time and computation

## Lifecycle Phases

CodingSessions progress through distinct phases:

1. **Initialization** - Establish goal and analyze starting state
2. **Active Development** - Execute tasks toward objective
3. **Checkpoint** - Persist progress at key milestones
4. **Completion** - Verify goal achievement and finalize
5. **Archival** - Preserve learnings for future reference

## State Management

Sessions maintain coherence through temporal continuity and spatial awareness:

- Conversation memory persists across Claude invocations
- File modification tracking maintains change history
- Pattern recognition accumulates across task executions
- Solution space refinement occurs through iterative development

# DevTask Mental Model

A DevTask represents a bounded transformation operation within a development
environment. It encapsulates a specific change to the codebase state, executed
through Claude Code's natural language interface.

## Relationship to CodingSession

DevTasks operate exclusively within the context of a CodingSession, inheriting
accumulated knowledge and contributing back to the session's evolving state.
This bidirectional relationship ensures:

**Context Inheritance**
- Tasks receive the session's accumulated file modification history
- Pattern discoveries from previous tasks inform current execution
- Decision rationale provides context for transformation choices

**State Contribution**
- Task results update the session's knowledge base
- Discovered constraints propagate to future tasks
- Verification outcomes influence subsequent operations

**Progressive Refinement**
- Each task builds upon previous session achievements
- Failed attempts inform alternative approaches
- Success patterns guide future task specifications

## Core Properties

**Transformation Specification**
- Intent expressed in natural language
- Scope defining affected codebase components
- Constraints establishing execution boundaries

**Execution Context**
- Environment container or workspace
- Working directory for file operations
- Session state providing accumulated knowledge

**Verification Contract**
- Success criteria for completion determination
- Validation strategy for correctness verification
- Rollback capability for change reversal

## Task Types

DevTasks organize into distinct categories based on their transformation intent:

- **Review** - Analyze code quality and suggest improvements
- **Implement** - Generate code meeting specifications
- **Test** - Create comprehensive test coverage
- **Refactor** - Restructure while preserving behavior
- **Document** - Add documentation and comments
- **Debug** - Identify and resolve issues

Each task type receives appropriate permissions and verification strategies
aligned with its purpose.

## Execution Lifecycle

Tasks progress through predictable phases:

1. **Specification** - Define intent and constraints
2. **Context Loading** - Gather relevant state
3. **Transformation** - Execute changes via Claude
4. **Verification** - Validate success criteria
5. **Integration** - Merge results into session

# Context Accumulation Model

The SessionContext maintains accumulated knowledge and state across task
executions. It represents the growing understanding of the codebase and
project conventions discovered through iterative development.

## Knowledge Categories

**Discovered Patterns**
- Code style conventions detected through analysis
- Architectural patterns observed in the codebase
- Testing strategies and coverage expectations

**Architectural Decisions**
- Design choices made during development
- Rationale for implementation approaches
- Trade-offs considered and rejected

**Verification History**
- Test execution results from each task
- Performance metrics and benchmarks
- Coverage reports and quality indicators

## Context Flow

When a DevTask executes within a CodingSession:

1. **Pre-execution Context Transfer**
   - Task inherits session's file modification history
   - Discovered patterns guide task approach
   - Previous verification results inform constraints
   - Session goal provides overarching direction

2. **Execution with Awareness**
   - Claude Code receives session context in prompts
   - File operations consider previous modifications
   - Pattern matching leverages accumulated knowledge
   - Decision making reflects session history

3. **Post-execution State Update**
   - Task results merge into session state
   - New patterns join discovered knowledge
   - File changes update modification tracking
   - Verification outcomes inform future tasks

## Information Persistence

The session maintains persistent Claude Code context through:
- Conversation continuity across task invocations
- Accumulated understanding of codebase structure
- Progressive refinement of solution approaches
- Historical awareness preventing repeated mistakes

# Implementation Notes

This module provides a simplified implementation focusing on core functionality.
The design prioritizes Git-based state management and Python configuration files
for human-readable persistence. Future iterations may expand to include automated
pattern discovery and cross-session learning mechanisms.
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
