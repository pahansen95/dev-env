"""Subprocess execution utilities

Provides robust subprocess management with timeout handling, output streaming,
and proper resource cleanup for external command execution.
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Callable
import logging
import sys

logger = logging.getLogger(__name__)


class SubprocessResult:
  """Encapsulates the result of a subprocess execution

  Provides structured access to process output, return codes, and execution
  metadata for consistent error handling and result processing.
  """

  def __init__(self, stdout: str, stderr: str, returncode: int, command: List[str], duration: Optional[float] = None):
    self.stdout = stdout
    self.stderr = stderr
    self.returncode = returncode
    self.command = command
    self.duration = duration

  @property
  def success(self) -> bool:
    """Check if the process completed successfully"""
    return self.returncode == 0

  @property
  def output(self) -> str:
    """Combined stdout and stderr output"""
    return f"{self.stdout}\n{self.stderr}".strip()

  def check(self) -> None:
    """Raise exception if process failed

    Raises:
        subprocess.CalledProcessError: Process returned non-zero exit code
    """
    if not self.success:
      raise subprocess.CalledProcessError(self.returncode, self.command, output=self.stdout, stderr=self.stderr)


class SubprocessRunner:
  """Manages subprocess execution with consistent error handling

  Provides both synchronous and asynchronous execution modes with timeout
  support, output streaming, and proper resource management.
  """

  @staticmethod
  def run(
    command: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    check: bool = True,
    capture_output: bool = True,
  ) -> SubprocessResult:
    """Execute subprocess synchronously

    Args:
        command: Command and arguments to execute
        cwd: Working directory for execution
        env: Environment variables (merged with current environment)
        timeout: Maximum execution time in seconds
        check: Raise exception on non-zero exit code
        capture_output: Capture stdout and stderr

    Returns:
        SubprocessResult with execution details

    Raises:
        subprocess.TimeoutExpired: Process exceeded timeout
        subprocess.CalledProcessError: Process failed and check=True
    """
    # Merge environment variables
    process_env = dict(os.environ)
    if env:
      process_env.update(env)

    logger.debug(f"Running command: {' '.join(command)}")
    start_time = time.time()

    try:
      if capture_output:
        result = subprocess.run(command, cwd=cwd, env=process_env, capture_output=True, text=True, timeout=timeout)
      else:
        result = subprocess.run(command, cwd=cwd, env=process_env, timeout=timeout)
        result.stdout = ""
        result.stderr = ""

      duration = time.time() - start_time

      subprocess_result = SubprocessResult(
        stdout=result.stdout, stderr=result.stderr, returncode=result.returncode, command=command, duration=duration
      )

      if check:
        subprocess_result.check()

      return subprocess_result

    except subprocess.TimeoutExpired:
      logger.error(f"Command timed out after {timeout}s: {' '.join(command)}")
      raise
    except subprocess.CalledProcessError as e:
      logger.error(f"Command failed with code {e.returncode}: {' '.join(command)}")
      if e.stderr:
        logger.error(f"Error output: {e.stderr}")
      raise

  @classmethod
  async def run_async(
    cls,
    command: List[str],
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    stdout_callback: Optional[Callable[[str], None]] = None,
    stderr_callback: Optional[Callable[[str], None]] = None,
  ) -> SubprocessResult:
    """Execute subprocess asynchronously with optional output streaming

    Args:
        command: Command and arguments to execute
        cwd: Working directory for execution
        env: Environment variables
        timeout: Maximum execution time in seconds
        stdout_callback: Function called for each stdout line
        stderr_callback: Function called for each stderr line

    Returns:
        SubprocessResult with execution details
    """
    # Merge environment variables
    process_env = dict(os.environ)
    if env:
      process_env.update(env)

    logger.debug(f"Running async command: {' '.join(command)}")
    start_time = time.time()

    # Create subprocess
    process = await asyncio.create_subprocess_exec(
      *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd, env=process_env
    )

    # Collect output
    stdout_lines = []
    stderr_lines = []

    async def read_stream(stream, lines, callback, stream_name):
      """Read from stream line by line"""
      while True:
        line = await stream.readline()
        if not line:
          break

        decoded_line = line.decode().rstrip()
        lines.append(decoded_line)

        if callback:
          try:
            callback(decoded_line)
          except Exception as e:
            logger.error(f"Callback error for {stream_name}: {e}")

    try:
      # Read both streams concurrently
      await asyncio.wait_for(
        asyncio.gather(
          read_stream(process.stdout, stdout_lines, stdout_callback, "stdout"),
          read_stream(process.stderr, stderr_lines, stderr_callback, "stderr"),
        ),
        timeout=timeout,
      )

      # Wait for process completion
      await asyncio.wait_for(process.wait(), timeout=1.0)

    except asyncio.TimeoutError:
      logger.error(f"Async command timed out after {timeout}s")
      process.kill()
      await process.wait()
      raise subprocess.TimeoutExpired(command, timeout)

    duration = time.time() - start_time

    return SubprocessResult(
      stdout="\n".join(stdout_lines),
      stderr="\n".join(stderr_lines),
      returncode=process.returncode,
      command=command,
      duration=duration,
    )

  @classmethod
  def check_command_exists(cls, command: str) -> bool:
    """Check if a command is available in PATH

    Args:
        command: Command name to check

    Returns:
        True if command exists, False otherwise
    """
    try:
      if sys.platform == "win32":
        # Windows: use 'where' command
        result = cls.run(["where", command], check=False, capture_output=True)
      else:
        # Unix: use 'which' command
        result = cls.run(["which", command], check=False, capture_output=True)

      return result.success
    except Exception:
      return False

  @classmethod
  def get_command_version(cls, command: str, version_flag: str = "--version") -> Optional[str]:
    """Get version string for a command

    Args:
        command: Command to check
        version_flag: Flag to get version (default: --version)

    Returns:
        Version string if available, None otherwise
    """
    try:
      result = cls.run([command, version_flag], check=False, capture_output=True, timeout=5.0)

      if result.success:
        return result.stdout.strip()

      # Some commands output version to stderr
      if result.stderr:
        return result.stderr.strip()

      return None

    except Exception as e:
      logger.debug(f"Failed to get version for {command}: {e}")
      return None


# Missing imports
import os
import time
