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
    # Log task execution start
    logger.info(f"Starting task execution: {self.id}")
    logger.info(f"Intent: {self.intent}")
    logger.debug(f"Session: {self.session_id}")
    logger.debug(f"Git state before: {self.before_commit[:8]}")

    # Ensure clean working directory
    stash_ref = None
    if not GitOperations.is_clean():
      # Parse git status to get file counts
      try:
        status_output = GitOperations.get_output(["status", "--porcelain=v1"])
        modified_count = 0
        untracked_count = 0

        for line in status_output.splitlines():
          if line:
            status_code = line[:2]
            if status_code[1] in "MD":  # Modified or Deleted in working tree
              modified_count += 1
            elif status_code == "??":  # Untracked
              untracked_count += 1

        logger.info(f"Working directory not clean - {modified_count} modified, {untracked_count} untracked files")
      except Exception as e:
        logger.warning(f"Could not parse git status: {e}")
        logger.info("Working directory not clean - stashing changes")
      logger.info(f"Stashing changes for task {self.id}")
      stash_ref = GitOperations.stash(f"Task {self.id}")

    try:
      # Execute Claude Code
      logger.info(f"Executing Claude Code with intent: {self.intent[:100]}{'...' if len(self.intent) > 100 else ''}")

      # Build command
      command = ["claude", "--print", self.intent]
      logger.debug(f"Command: {' '.join(command[:3])}... (intent length: {len(self.intent)} chars)")

      # Log execution environment
      import os

      logger.debug(f"Working directory: {os.getcwd()}")
      logger.debug(f"Python environment: {os.environ.get('VIRTUAL_ENV', 'No venv active')}")

      start_time = datetime.now()
      try:
        # Execute with progress logging
        logger.info("Starting Claude Code subprocess (timeout: 15 minutes)...")
        result = SubprocessRunner.run(
          command=command,
          timeout=900,  # 15m
          check=False,
          capture_output=True,  # Ensure we capture both stdout and stderr
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Claude Code execution completed in {elapsed:.1f} seconds")

      except TimeoutError as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"Claude Code execution timed out after {elapsed:.1f} seconds")
        logger.error(f"Timeout details: {str(e)}")
        raise RuntimeError(
          f"Task timed out after {elapsed:.1f}s. Consider breaking down the intent into smaller steps."
        )

      except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"Claude Code execution failed after {elapsed:.1f} seconds")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        raise RuntimeError(f"Failed to execute Claude Code: {type(e).__name__}: {str(e)}")

      # Process results
      self.output = result.stdout
      self.success = result.success

      # Log execution results
      logger.info(f"Claude Code exit status: {'SUCCESS' if self.success else 'FAILURE'}")
      if result.stderr:
        logger.warning(f"Claude Code stderr output: {result.stderr[:500]}{'...' if len(result.stderr) > 500 else ''}")

      if self.output:
        output_lines = self.output.strip().split("\n")
        logger.debug(f"Claude Code output ({len(output_lines)} lines, {len(self.output)} chars total)")
        if len(output_lines) <= 10:
          logger.debug(f"Output:\n{self.output}")
        else:
          logger.debug(f"Output (first 5 lines):\n{chr(10).join(output_lines[:5])}")
          logger.debug(f"... ({len(output_lines) - 10} lines omitted) ...")
          logger.debug(f"Output (last 5 lines):\n{chr(10).join(output_lines[-5:])}")
      else:
        logger.warning("Claude Code produced no output")

      # Check for changes and commit if successful
      if self.success:
        if not GitOperations.is_clean():
          # Get detailed change information by parsing git status
          try:
            status_output = GitOperations.get_output(["status", "--porcelain=v1"])
            change_count = 0
            change_types = {"staged": 0, "modified": 0, "untracked": 0}

            for line in status_output.splitlines():
              if line:
                change_count += 1
                status_code = line[:2]
                if status_code[0] in "AMD":  # Staged changes
                  change_types["staged"] += 1
                if status_code[1] in "MD":  # Modified in working tree
                  change_types["modified"] += 1
                elif status_code == "??":  # Untracked
                  change_types["untracked"] += 1

            change_summary = ", ".join([f"{count} {type}" for type, count in change_types.items() if count > 0])
            logger.debug(f"Change breakdown: {change_summary}")

          except Exception as e:
            logger.warning(f"Could not parse git status for details: {e}")
            change_count = 1  # At least one change since not clean

          logger.info(f"Detected {change_count} file changes after task execution")

          # Stage and commit
          GitOperations.stage_all()
          logger.info("Staged all changes")

          commit_msg = f"Task: {self.intent[:50]}{'...' if len(self.intent) > 50 else ''}"
          commit_body = f"task_id: {self.id}\nsession_id: {self.session_id}\n\nIntent:\n{self.intent}"

          self.after_commit = GitOperations.commit(commit_msg, body=commit_body)
          logger.info(f"Created commit {self.after_commit[:8]}: {commit_msg}")
        else:
          logger.info("No changes detected after successful execution")
          self.after_commit = self.before_commit
      else:
        logger.warning("Task failed - no changes will be committed")
        self.after_commit = self.before_commit

        # Try to extract error information from output
        if self.output and "error" in self.output.lower():
          error_lines = [line for line in self.output.split("\n") if "error" in line.lower()]
          if error_lines:
            logger.error(f"Error indicators in output: {error_lines[:3]}")

    except Exception as e:
      logger.error(f"Task execution failed with exception: {type(e).__name__}")
      logger.error(f"Exception details: {str(e)}")

      # Add more context to the error
      import traceback

      logger.debug(f"Full traceback:\n{traceback.format_exc()}")

      self.success = False
      self.output = f"Error: {type(e).__name__}: {str(e)}"

      # Try to capture any partial work
      if not GitOperations.is_clean():
        try:
          status_output = GitOperations.get_output(["status", "--porcelain=v1", "--untracked-files=normal"])
          change_lines = [line for line in status_output.splitlines() if line.strip()]
          if change_lines:
            logger.warning(f"Partial changes detected: {len(change_lines)} files affected")
            # Log first few files for context
            for line in change_lines[:5]:
              file_path = line[3:]
              status = line[:2]
              logger.debug(f"  {status} {file_path}")
            if len(change_lines) > 5:
              logger.debug(f"  ... and {len(change_lines) - 5} more files")
        except Exception as e:
          logger.warning(f"Could not analyze partial changes: {e}")

    finally:
      # Restore stashed changes
      if stash_ref:
        try:
          GitOperations.run_command(["stash", "pop"])
          logger.info("Successfully restored stashed changes")
        except Exception as e:
          logger.error(f"Failed to restore stash: {type(e).__name__}: {e}")
          logger.error("Manual stash recovery may be needed")
          logger.error(f"Stash reference: {stash_ref}")

      # Final status log
      logger.info(f"Task {self.id} completed: {'SUCCESS' if self.success else 'FAILURE'}")
      logger.debug(f"Final git state: {GitOperations.get_current_commit()[:8]}")

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

    try:
      data = PythonConfigSerializer.read_config(path, "SESSION")
    except SyntaxError as e:
      logger.error(f"Session file {path} has invalid Python syntax: {e}")
      raise ValueError(f"Session {session_id} file is corrupted with syntax error at line {e.lineno}: {e.msg}") from e
    except Exception as e:
      logger.error(f"Failed to load session {session_id}: {type(e).__name__}: {e}")
      raise ValueError(f"Session {session_id} could not be loaded: {type(e).__name__}: {str(e)}") from e

    # Validate required fields
    required_fields = ["id", "goal", "created_at", "start_commit"]
    missing = [field for field in required_fields if field not in data]
    if missing:
      raise ValueError(f"Session {session_id} is missing required fields: {', '.join(missing)}")

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

        # Validate required fields
        if not all(field in data for field in ["id", "goal", "created_at"]):
          logger.warning(f"Skipping incomplete session file {path}")
          continue

        sessions.append(
          {
            "id": data["id"],
            "goal": data["goal"],
            "created_at": data["created_at"],
            "task_count": len(data.get("tasks", [])),
          }
        )
      except SyntaxError as e:
        logger.error(f"Skipping session {path} with syntax error at line {e.lineno}: {e.msg}")
        continue
      except Exception as e:
        logger.warning(f"Failed to load session from {path}: {type(e).__name__}: {e}")
        continue

    return sorted(sessions, key=lambda s: s["created_at"], reverse=True)
