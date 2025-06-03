"""Claude Code subprocess execution management"""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class ClaudeCodeOutput:
  """Structured output from Claude Code execution"""

  def __init__(self, stdout: str, stderr: str, return_code: int):
    self.stdout = stdout
    self.stderr = stderr
    self.return_code = return_code
    self.timestamp = datetime.now()

    # Parse structured output if present
    self.files_modified: List[str] = []
    self.files_created: List[str] = []
    self.tests_run: int = 0
    self.tests_passed: int = 0

    self._parse_output()

  def _parse_output(self):
    """Extract structured information from Claude output"""
    # Look for common patterns in Claude's output
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
      "timestamp": self.timestamp.isoformat(),
      "files_modified": self.files_modified,
      "files_created": self.files_created,
      "tests_run": self.tests_run,
      "tests_passed": self.tests_passed,
    }


class ClaudeCodeExecutor:
  """Manages Claude Code subprocess execution"""

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
    prompt = self._build_prompt(intent, context)

    logger.info(f"Executing Claude Code with intent: {intent[:100]}...")

    try:
      # Execute with timeout
      process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=self.working_directory,
        env={**self.environment, "CLAUDE_CODE_INTENT": intent},
      )

      stdout, stderr = process.communicate(input=prompt, timeout=self.timeout)

      output = ClaudeCodeOutput(stdout, stderr, process.returncode)

      if output.success:
        logger.info("Claude Code completed successfully")
      else:
        logger.warning(f"Claude Code failed with return code {output.return_code}")

      return output

    except subprocess.TimeoutExpired:
      logger.error(f"Claude Code execution timed out after {self.timeout}s")
      process.kill()
      stdout, stderr = process.communicate()
      return ClaudeCodeOutput(stdout or "", f"Process timed out after {self.timeout} seconds\n{stderr or ''}", -1)
    except Exception as e:
      logger.error(f"Failed to execute Claude Code: {e}")
      return ClaudeCodeOutput("", str(e), -1)

  def _build_prompt(self, intent: str, context: Optional[str]) -> str:
    """Build comprehensive prompt for Claude"""
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
    """Async execution with optional output streaming"""
    cmd = ["claude-code", "--non-interactive"]
    prompt = self._build_prompt(intent, context)

    logger.info("Starting async Claude Code execution")

    try:
      process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=self.working_directory,
        env={**self.environment, "CLAUDE_CODE_INTENT": intent},
      )

      if stream_output:
        # Stream output in real-time
        stdout_lines = []
        stderr_lines = []

        async def read_stream(stream, lines, prefix):
          async for line in stream:
            decoded = line.decode().rstrip()
            lines.append(decoded)
            logger.info(f"{prefix}: {decoded}")

        # Start reading both streams
        await asyncio.gather(
          read_stream(process.stdout, stdout_lines, "STDOUT"), read_stream(process.stderr, stderr_lines, "STDERR")
        )

        await process.wait()

        return ClaudeCodeOutput("\n".join(stdout_lines), "\n".join(stderr_lines), process.returncode)
      else:
        # Wait for completion
        stdout, stderr = await asyncio.wait_for(process.communicate(prompt.encode()), timeout=self.timeout)

        return ClaudeCodeOutput(
          stdout.decode() if stdout else "", stderr.decode() if stderr else "", process.returncode
        )

    except asyncio.TimeoutError:
      logger.error("Async Claude Code execution timed out")
      process.kill()
      await process.wait()
      return ClaudeCodeOutput("", f"Timed out after {self.timeout}s", -1)

  def validate_environment(self) -> Tuple[bool, str]:
    """Check if Claude Code is available and properly configured"""
    try:
      result = subprocess.run(["claude-code", "--version"], capture_output=True, text=True, timeout=5)

      if result.returncode == 0:
        return True, f"Claude Code available: {result.stdout.strip()}"
      else:
        return False, f"Claude Code check failed: {result.stderr}"

    except subprocess.TimeoutExpired:
      return False, "Claude Code version check timed out"
    except FileNotFoundError:
      return False, "Claude Code not found in PATH"
    except Exception as e:
      return False, f"Error checking Claude Code: {e}"
