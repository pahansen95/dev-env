"""Logging configuration utilities

Provides centralized logging setup for the MCP Project Integration,
including file logging capabilities for debugging and audit trails.
"""

import logging
import os
from pathlib import Path


def add_file_logging(log_file: str) -> None:
  """Add file handler to existing logger configuration

  Configures a file handler for persistent logging, creating necessary
  directories and using consistent formatting across all loggers.

  Args:
      log_file: Path to the log file
  """
  # Create log directory if needed
  log_path = Path(log_file)
  log_path.parent.mkdir(parents=True, exist_ok=True)

  # Create file handler with consistent format
  file_handler = logging.FileHandler(log_file, mode="a")
  file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
  file_handler.setLevel(logging.DEBUG)  # Capture all levels

  # Add to root logger to capture all logs
  root_logger = logging.getLogger()
  root_logger.addHandler(file_handler)

  # Log session start
  logger = logging.getLogger(__name__)
  logger.info(f"=== MCP Server Started - PID: {os.getpid()} ===")
  file_handler.flush()


def configure_console_logging(level: int = logging.INFO) -> None:
  """Configure console logging with standard format

  Sets up console logging for immediate feedback during development
  and operation.

  Args:
      level: Logging level for console output
  """
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
  console_handler.setLevel(level)

  root_logger = logging.getLogger()
  root_logger.addHandler(console_handler)
  root_logger.setLevel(level)
