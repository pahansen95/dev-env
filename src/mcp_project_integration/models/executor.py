"""Claude Code subprocess execution management

Manages Claude Code process execution with structured output parsing and
conversation history persistence. Provides both synchronous and asynchronous
execution modes with proper timeout handling.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

from ..core.utils import SubprocessRunner, SubprocessResult

logger = logging.getLogger(__name__)


class ClaudeCodeOutput:
  """Structured output from Claude Code execution

  Parses and encapsulates Claude Code execution results, extracting file
  operations and test results from unstructured output.
  """

  def __init__(self, result: SubprocessResult):
    self.stdout = result.stdout
    self.stderr = result.stderr
    self.return_code = result.returncode
    self.duration = result.duration
    self.timestamp = datetime.now()

    # Parse structured output if present
    self.files_modified: List[str] = []
    self.files_created: List[str] = []
    self.tests_run: int = 0
    self.tests_passed: int = 0

    self._parse_output()

  def _parse_output(self):
    """Extract structured information from Claude output"""
    lines = self.stdout.splitlines()

    for line in lines:
      # File operations
      if "Created file:" in line or "Creating:" in line:
        parts = line.split(":", 1)
        if len(parts) > 1:
          filepath = parts[1].strip()
          self.files_created.append(filepath)

      elif "Modified file:" in line or "Updating:" in line:
        parts = line.split(":", 1)
        if len(parts) > 1:
          filepath = parts[1].strip()
          self.files_modified.append(filepath)

      # Test results
      elif "tests passed" in line.lower():
        # Extract test counts (various formats)
        import re

        numbers = re.findall(r"\d+", line)
        if len(numbers) >= 2:
          self.tests_passed = int(numbers[0])
          self.tests_run = int(numbers[-1])

  @property
  def success(self) -> bool:
    """Check if execution was successful"""
    return self.return_code == 0

  def to_dict(self) -> Dict:
    """Convert to dictionary for persistence"""
    return {
      "stdout": self.stdout,
      "stderr": self.stderr,
      "return_code": self.return_code,
      "duration": self.duration,
      "timestamp": self.timestamp,
      "files_modified": self.files_modified,
      "files_created": self.files_created,
      "tests_run": self.tests_run,
      "tests_passed": self.tests_passed,
    }


class ClaudeCodeExecutor:
  """Manages Claude Code subprocess execution

  Provides a controlled execution environment for Claude Code with context
  management, timeout handling, and output parsing.
  """

  def __init__(
    self,
    working_directory: Optional[Path] = None,
    timeout: int = 300,  # 5 minutes default
    environment: Optional[Dict[str, str]] = None,
  ):
    self.working_directory = working_directory or Path.cwd()
    self.timeout = timeout
    self.environment = environment or {}

  def run(self, intent: str, context: Optional[str] = None, interactive: bool = False) -> ClaudeCodeOutput:
    """Execute Claude Code with given intent

    Args:
        intent: Natural language task description
        context: Additional context to provide
        interactive: Whether to run in interactive mode

    Returns:
        Structured output from execution
    """
    # Build command
    cmd = ["claude-code"]

    if not interactive:
      cmd.append("--non-interactive")

    # Prepare prompt with context
    _prompt = self._build_prompt(intent, context)

    logger.info(f"Executing Claude Code with intent: {intent[:100]}...")

    # Set up environment
    env = dict(self.environment)
    env["CLAUDE_CODE_INTENT"] = intent

    # Execute using SubprocessRunner
    result = SubprocessRunner.run(
      command=cmd, cwd=self.working_directory, env=env, timeout=self.timeout, check=False, capture_output=True
    )

    output = ClaudeCodeOutput(result)

    if output.success:
      logger.info(f"Claude Code completed successfully in {output.duration:.1f}s")
    else:
      logger.warning(f"Claude Code failed with return code {output.return_code}")

    return output

  def _build_prompt(self, intent: str, context: Optional[str]) -> str:
    """Build comprehensive prompt for Claude

    Structures the prompt to provide clear context and instructions
    for Claude Code execution.
    """
    parts = []

    # Add context if provided
    if context:
      parts.append("## Context")
      parts.append(context)
      parts.append("")

    # Add intent
    parts.append("## Task")
    parts.append(intent)
    parts.append("")

    # Add instructions
    parts.append("## Instructions")
    parts.append("- Follow existing code patterns and conventions")
    parts.append("- Ensure all changes are tested")
    parts.append("- Provide clear explanations for changes")

    return "\n".join(parts)

  async def run_async(
    self, intent: str, context: Optional[str] = None, stream_output: bool = False
  ) -> ClaudeCodeOutput:
    """Async execution with optional output streaming

    Args:
        intent: Natural language task description
        context: Additional context
        stream_output: Stream output line-by-line

    Returns:
        Structured output from execution
    """
    cmd = ["claude-code", "--non-interactive"]

    # Set up environment
    env = dict(self.environment)
    env["CLAUDE_CODE_INTENT"] = intent

    logger.info("Starting async Claude Code execution")

    if stream_output:
      # Define callbacks for streaming
      def stdout_callback(line: str):
        logger.info(f"Claude: {line}")

      def stderr_callback(line: str):
        logger.warning(f"Claude Error: {line}")

      result = await SubprocessRunner.run_async(
        command=cmd,
        cwd=self.working_directory,
        env=env,
        timeout=self.timeout,
        stdout_callback=stdout_callback,
        stderr_callback=stderr_callback,
      )
    else:
      result = await SubprocessRunner.run_async(command=cmd, cwd=self.working_directory, env=env, timeout=self.timeout)

    return ClaudeCodeOutput(result)

  def validate_environment(self) -> Tuple[bool, str]:
    """Check if Claude Code is available and properly configured

    Returns:
        Tuple of (is_valid, message)
    """
    if not SubprocessRunner.check_command_exists("claude-code"):
      return False, "Claude Code not found in PATH"

    version = SubprocessRunner.get_command_version("claude-code")
    if version:
      return True, f"Claude Code available: {version}"
    else:
      return True, "Claude Code available (version unknown)"
