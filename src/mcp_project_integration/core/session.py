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
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
import os

from .serialization import PythonConfigSerializer
from .utils import GitOperations, SubprocessRunner

logger = logging.getLogger(__name__)


class ClaudeCodeOutput:
  """Parses and stores Claude Code's structured output"""

  def __init__(self, raw_output: str):
    self.raw_output = raw_output
    self.messages: List[Dict[str, Any]] = []
    self.session_id: Optional[str] = None
    self.tools_available: List[str] = []
    self.total_cost: Optional[float] = None
    self.duration_ms: Optional[int] = None
    self.num_turns: Optional[int] = None
    self.final_result: Optional[str] = None
    self.error: Optional[str] = None
    self._parse()

  def _parse(self):
    """Parse JSON lines from Claude Code output"""
    lines = self.raw_output.strip().split("\n")

    for line in lines:
      if not line.strip():
        continue

      try:
        msg = json.loads(line)
        self.messages.append(msg)

        # Extract key information based on message type
        msg_type = msg.get("type")

        if msg_type == "system" and msg.get("subtype") == "init":
          self.session_id = msg.get("session_id")
          self.tools_available = msg.get("tools", [])

        elif msg_type == "result":
          result_data = msg
          self.total_cost = result_data.get("cost_usd")
          self.duration_ms = result_data.get("duration_ms")
          self.num_turns = result_data.get("num_turns")
          self.final_result = result_data.get("result")
          self.error = result_data.get("error")

      except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON line: {line[:100]}... Error: {e}")
        continue

  def get_tool_usage(self) -> List[Dict[str, Any]]:
    """Extract tool usage from messages"""
    tool_usage = []

    for msg in self.messages:
      if msg.get("type") == "assistant":
        content = msg.get("message", {}).get("content", [])
        for item in content:
          if item.get("type") == "tool_use":
            tool_usage.append({"id": item.get("id"), "name": item.get("name"), "input": item.get("input", {})})

    return tool_usage

  def get_conversation_flow(self) -> List[Dict[str, Any]]:
    """Extract simplified conversation flow"""
    flow = []

    for msg in self.messages:
      msg_type = msg.get("type")

      if msg_type == "assistant":
        content = msg.get("message", {}).get("content", [])
        for item in content:
          if item.get("type") == "text":
            flow.append({"role": "assistant", "type": "text", "content": item.get("text", "")})
          elif item.get("type") == "tool_use":
            flow.append(
              {"role": "assistant", "type": "tool_use", "tool": item.get("name"), "input": item.get("input", {})}
            )

      elif msg_type == "user":
        content = msg.get("message", {}).get("content", [])
        for item in content:
          if item.get("type") == "tool_result":
            flow.append(
              {
                "role": "user",
                "type": "tool_result",
                "tool_id": item.get("tool_use_id"),
                "content": item.get("content", "")[:200] + "..."
                if len(item.get("content", "")) > 200
                else item.get("content", ""),
              }
            )

    return flow

  def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary for storage"""
    return {
      "session_id": self.session_id,
      "tools_available": self.tools_available,
      "total_cost": self.total_cost,
      "duration_ms": self.duration_ms,
      "num_turns": self.num_turns,
      "final_result": self.final_result,
      "error": self.error,
      "tool_usage": self.get_tool_usage(),
      "conversation_flow": self.get_conversation_flow(),
      "message_count": len(self.messages),
    }


class Task:
  """Enhanced Task with verbose Claude Code output capture"""

  def __init__(self, intent: str, session_id: str):
    self.id = str(uuid.uuid4())
    self.session_id = session_id
    self.intent = intent
    self.created_at = datetime.now()
    self.before_commit = GitOperations.get_current_commit()
    self.after_commit: Optional[str] = None
    self.success: Optional[bool] = None
    self.raw_output: Optional[str] = None
    self.parsed_output: Optional[ClaudeCodeOutput] = None
    self.execution_metadata: Dict[str, Any] = {}

  def execute(self) -> bool:
    """Execute Claude Code with verbose output capture"""
    # Log task execution start
    logger.info(f"Starting task execution: {self.id}")
    logger.info(f"Intent: {self.intent}")
    logger.debug(f"Session: {self.session_id}")
    logger.debug(f"Git state before: {self.before_commit[:8]}")

    # Track execution timing
    execution_start = datetime.now()

    # Ensure clean working directory
    stash_ref = None
    if not GitOperations.is_clean():
      # Get detailed status
      try:
        status_output = GitOperations.get_output(["status", "--porcelain=v1"])
        changes = self._parse_git_status(status_output)
        logger.info(f"Working directory not clean - {changes['summary']}")
        self.execution_metadata["pre_execution_changes"] = changes
      except Exception as e:
        logger.warning(f"Could not parse git status: {e}")

      logger.info(f"Stashing changes for task {self.id}")
      stash_ref = GitOperations.stash(f"Task {self.id}")

    try:
      # Execute Claude Code with verbose output
      logger.info(f"Executing Claude Code with intent: {self.intent[:100]}{'...' if len(self.intent) > 100 else ''}")

      # Build command with verbose output flags
      command = [
        "claude",
        "--verbose",  # Enable verbose output
        "--print",  # Print results
        "--output-format",
        "stream-json",  # Structured JSON output
        self.intent,
      ]

      logger.debug(f"Command: {' '.join(command[:7])}... (intent length: {len(self.intent)} chars)")

      logger.debug(f"Working directory: {os.getcwd()}")
      logger.debug(f"Python environment: {os.environ.get('VIRTUAL_ENV', 'No venv active')}")

      # Execute with progress logging
      logger.info("Starting Claude Code subprocess (timeout: 15 minutes)...")

      try:
        result = SubprocessRunner.run(
          command=command,
          timeout=900,  # 15 minutes
          check=False,
          capture_output=True,
        )

        execution_time = (datetime.now() - execution_start).total_seconds()
        logger.info(f"Claude Code execution completed in {execution_time:.1f} seconds")
        self.execution_metadata["execution_time_seconds"] = execution_time

      except TimeoutError:
        execution_time = (datetime.now() - execution_start).total_seconds()
        logger.error(f"Claude Code execution timed out after {execution_time:.1f} seconds")
        self.execution_metadata["timeout"] = True
        self.execution_metadata["execution_time_seconds"] = execution_time
        raise RuntimeError(
          f"Task timed out after {execution_time:.1f}s. Consider breaking down the intent into smaller steps."
        )

      except Exception as e:
        execution_time = (datetime.now() - execution_start).total_seconds()
        logger.error(f"Claude Code execution failed after {execution_time:.1f} seconds")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        self.execution_metadata["execution_error"] = f"{type(e).__name__}: {str(e)}"
        self.execution_metadata["execution_time_seconds"] = execution_time
        raise RuntimeError(f"Failed to execute Claude Code: {type(e).__name__}: {str(e)}")

      # Store raw output
      self.raw_output = result.stdout
      self.success = result.success

      # Parse structured output
      if self.raw_output:
        logger.debug(f"Parsing Claude Code output ({len(self.raw_output)} chars)")
        self.parsed_output = ClaudeCodeOutput(self.raw_output)

        # Log parsed information
        if self.parsed_output.session_id:
          logger.info(f"Claude Code session ID: {self.parsed_output.session_id}")
        if self.parsed_output.tools_available:
          logger.debug(
            f"Available tools: {', '.join(self.parsed_output.tools_available[:5])}{'...' if len(self.parsed_output.tools_available) > 5 else ''}"
          )
        if self.parsed_output.total_cost is not None:
          logger.info(f"Execution cost: ${self.parsed_output.total_cost:.6f}")
        if self.parsed_output.duration_ms is not None:
          logger.info(f"Claude API duration: {self.parsed_output.duration_ms}ms")
        if self.parsed_output.num_turns is not None:
          logger.info(f"Conversation turns: {self.parsed_output.num_turns}")

        # Log tool usage
        tool_usage = self.parsed_output.get_tool_usage()
        if tool_usage:
          logger.info(f"Tools used: {len(tool_usage)} invocations")
          for tool in tool_usage[:3]:  # Log first 3
            logger.debug(f"  - {tool['name']}: {str(tool['input'])[:100]}")
          if len(tool_usage) > 3:
            logger.debug(f"  ... and {len(tool_usage) - 3} more tool invocations")

        # Store metadata
        self.execution_metadata.update(self.parsed_output.to_dict())

      else:
        logger.warning("Claude Code produced no output")

      # Log stderr if present
      if result.stderr:
        logger.warning(f"Claude Code stderr output: {result.stderr[:500]}{'...' if len(result.stderr) > 500 else ''}")
        self.execution_metadata["stderr"] = result.stderr

      # Check for changes and commit if successful
      if self.success:
        if not GitOperations.is_clean():
          # Get detailed change information
          status_output = GitOperations.get_output(["status", "--porcelain=v1"])
          changes = self._parse_git_status(status_output)
          logger.info(f"Detected changes after execution: {changes['summary']}")
          self.execution_metadata["post_execution_changes"] = changes

          # Get diff summary
          diff_stats = GitOperations.get_output(["diff", "--stat"])
          if diff_stats:
            logger.debug("Change statistics:")
            for line in diff_stats.split("\n")[:10]:  # First 10 lines
              if line.strip():
                logger.debug(f"  {line}")

          # Stage and commit
          GitOperations.stage_all()
          logger.info("Staged all changes")

          commit_msg = f"Task: {self.intent[:50]}{'...' if len(self.intent) > 50 else ''}"
          commit_body = self._build_commit_body()

          self.after_commit = GitOperations.commit(commit_msg, body=commit_body)
          logger.info(f"Created commit {self.after_commit[:8]}: {commit_msg}")
        else:
          logger.info("No changes detected after successful execution")
          self.after_commit = self.before_commit
      else:
        logger.warning("Task failed - no changes will be committed")
        self.after_commit = self.before_commit

        # Extract error information from parsed output
        if self.parsed_output and self.parsed_output.error:
          logger.error(f"Claude Code reported error: {self.parsed_output.error}")

    except Exception as e:
      logger.error(f"Task execution failed with exception: {type(e).__name__}")
      logger.error(f"Exception details: {str(e)}")

      import traceback

      logger.debug(f"Full traceback:\n{traceback.format_exc()}")

      self.success = False
      self.execution_metadata["exception"] = f"{type(e).__name__}: {str(e)}"

      # Check for partial work
      if not GitOperations.is_clean():
        try:
          status_output = GitOperations.get_output(["status", "--porcelain=v1"])
          changes = self._parse_git_status(status_output)
          logger.warning(f"Partial changes detected: {changes['summary']}")
          self.execution_metadata["partial_changes"] = changes
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
          self.execution_metadata["stash_restore_failed"] = True

      # Final status log
      execution_time = (datetime.now() - execution_start).total_seconds()
      logger.info(f"Task {self.id} completed in {execution_time:.1f}s: {'SUCCESS' if self.success else 'FAILURE'}")
      logger.debug(f"Final git state: {GitOperations.get_current_commit()[:8]}")

    return self.success

  def _parse_git_status(self, status_output: str) -> Dict[str, Any]:
    """Parse git status output into structured format"""
    changes = {"staged": [], "modified": [], "untracked": [], "deleted": [], "total": 0}

    for line in status_output.splitlines():
      if not line:
        continue

      status_code = line[:2]
      file_path = line[3:]
      changes["total"] += 1

      if status_code[0] in "AMD":  # Staged changes
        changes["staged"].append(file_path)
      if status_code[1] == "M":  # Modified in working tree
        changes["modified"].append(file_path)
      elif status_code[1] == "D":  # Deleted in working tree
        changes["deleted"].append(file_path)
      elif status_code == "??":  # Untracked
        changes["untracked"].append(file_path)

    # Build summary
    summary_parts = []
    if changes["staged"]:
      summary_parts.append(f"{len(changes['staged'])} staged")
    if changes["modified"]:
      summary_parts.append(f"{len(changes['modified'])} modified")
    if changes["untracked"]:
      summary_parts.append(f"{len(changes['untracked'])} untracked")
    if changes["deleted"]:
      summary_parts.append(f"{len(changes['deleted'])} deleted")

    changes["summary"] = ", ".join(summary_parts) if summary_parts else "no changes"

    return changes

  def _build_commit_body(self) -> str:
    """Build detailed commit message body"""
    body_parts = [f"task_id: {self.id}", f"session_id: {self.session_id}", "", "Intent:", self.intent, ""]

    # Add execution metadata
    if self.parsed_output:
      body_parts.extend(
        [
          "Execution Details:",
          f"- Claude session: {self.parsed_output.session_id or 'N/A'}",
          f"- Cost: ${self.parsed_output.total_cost:.6f}" if self.parsed_output.total_cost else "- Cost: N/A",
          f"- Duration: {self.parsed_output.duration_ms}ms" if self.parsed_output.duration_ms else "- Duration: N/A",
          f"- Turns: {self.parsed_output.num_turns}" if self.parsed_output.num_turns else "- Turns: N/A",
          "",
        ]
      )

      # Add tool usage summary
      tool_usage = self.parsed_output.get_tool_usage()
      if tool_usage:
        body_parts.append("Tools Used:")
        tool_counts = {}
        for tool in tool_usage:
          tool_name = tool["name"]
          tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        for tool_name, count in sorted(tool_counts.items()):
          body_parts.append(f"- {tool_name}: {count}x")
        body_parts.append("")

    return "\n".join(body_parts)

  def to_dict(self) -> Dict:
    """Convert task to dictionary for persistence with verbose output"""
    base_dict = {
      "id": self.id,
      "intent": self.intent,
      "created_at": self.created_at,
      "before_commit": self.before_commit,
      "after_commit": self.after_commit,
      "success": self.success,
      "execution_metadata": self.execution_metadata,
    }

    # Add parsed output summary
    if self.parsed_output:
      base_dict["claude_output"] = {
        "session_id": self.parsed_output.session_id,
        "cost_usd": self.parsed_output.total_cost,
        "duration_ms": self.parsed_output.duration_ms,
        "num_turns": self.parsed_output.num_turns,
        "tool_count": len(self.parsed_output.get_tool_usage()),
        "final_result": self.parsed_output.final_result[:500] if self.parsed_output.final_result else None,
        "error": self.parsed_output.error,
      }

    return base_dict


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
