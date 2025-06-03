"""CLI commands for MCP Project Integration"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from .utils import find_git_root, get_git_project_name, add_file_logging
from .server import mcp

logger = logging.getLogger(__name__)


def install_command(args):
  """Install the MCP server in Claude Desktop"""
  logger.info("Starting Claude Desktop installation")

  # Find git project root - fail if not in git repo
  project_root = find_git_root()
  logger.info(f"Found git project root: {project_root}")

  # Check for .venv in project root
  venv_path = project_root / ".venv"
  if not venv_path.is_dir():
    raise FileNotFoundError(
      f"No .venv directory found at {project_root}\nPlease create a virtual environment with: python -m venv .venv"
    )

  # Get project name from git
  git_project_name = get_git_project_name()
  logger.info(f"Detected project name from git: {git_project_name}")

  # Get Claude Desktop config path
  if sys.platform == "darwin":  # macOS
    config_dir = Path.home() / "Library" / "Application Support" / "Claude"
  elif sys.platform.startswith("linux"):
    xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    config_dir = Path(xdg_config) / "Claude"
  else:
    raise OSError(f"Unsupported platform: {sys.platform}")

  if not config_dir.exists():
    raise FileNotFoundError(
      f"Claude Desktop config directory not found: {config_dir}\n"
      "Please ensure Claude Desktop is installed and run at least once"
    )

  config_file = config_dir / "claude_desktop_config.json"
  logger.info(f"Claude config file: {config_file}")

  # Load existing config or create new one
  if config_file.exists():
    with open(config_file, "r") as f:
      config = json.load(f)
    logger.info("Loaded existing Claude config")
  else:
    config = {}

  # Ensure mcpServers section exists
  if "mcpServers" not in config:
    config["mcpServers"] = {}

  # Get the current script path
  script_path = Path(sys.argv[0]).resolve()

  # Configure the server entry
  server_name = args.name or git_project_name

  # Determine Python executable path based on platform
  if sys.platform == "win32":
    python_executable = project_root / ".venv" / "Scripts" / "python.exe"
  else:
    python_executable = project_root / ".venv" / "bin" / "python"

  server_config = {"command": str(python_executable), "args": [str(script_path)], "cwd": str(project_root)}

  # Add dev mode configuration
  if args.dev:
    logger.info("Configuring server for development mode")
    # Add verbose flag and log file before run command
    log_file_path = project_root / ".cache" / "mcp.log"
    server_config["args"].extend(
      [
        "-v",  # Verbose logging
        "-l",
        str(log_file_path),  # Log to file
      ]
    )
    logger.info(f"Development logs will be written to: {log_file_path}")

  # Add run subcommand after global flags
  server_config["args"].extend(["run", str(project_root)])

  # Add environment variables if needed
  if args.env:
    server_config["env"] = dict(env.split("=", 1) for env in args.env)

  config["mcpServers"][server_name] = server_config

  # Write updated config
  with open(config_file, "w") as f:
    json.dump(config, f, indent=2)

  logger.info(f"Successfully installed server '{server_name}' in Claude Desktop")
  logger.info(f"Using Python from: {server_config['command']}")
  logger.info(f"Working directory: {server_config['cwd']}")
  logger.info(f"Git project: {git_project_name}")


def run_command(args):
  """Run the MCP server"""
  logger.info("Starting MCP server")
  logger.info(f"Initial working directory: {os.getcwd()}")
  logger.info(f"Python executable: {sys.executable}")

  # Change to project directory
  project_dir = Path(args.project_dir).resolve()
  if not project_dir.exists():
    raise FileNotFoundError(f"Project directory not found: {project_dir}")

  os.chdir(project_dir)
  logger.info(f"Changed working directory to: {os.getcwd()}")

  # Verify we're in a git repository
  try:
    git_root = find_git_root()
    logger.info(f"Git project root: {git_root}")
    git_name = get_git_project_name()
    logger.info(f"Git project name: {git_name}")
  except subprocess.CalledProcessError:
    raise RuntimeError(f"Directory is not a git repository: {project_dir}")

  # Set log level based on verbosity
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

  # Run with stdio transport - let exceptions bubble up
  logger.info("Starting stdio transport")
  mcp.run(transport="stdio")


def validate_command(args):
  """Validate the MCP server configuration and syntax"""
  logger.info("Validating MCP server")

  # If we got here, imports worked and syntax is valid
  try:
    # Quick validation - just check if we can access the MCP server instance
    logger.info(f"MCP server name: {mcp.name}")
    logger.info("✓ Validation successful - server configuration is valid")
  except Exception as e:
    logger.error(f"Validation failed: {e}")
    sys.exit(1)


def main():
  """Main CLI entry point"""
  parser = argparse.ArgumentParser(description="MCP Project Integration - Connect Claude Desktop to local projects")

  # Global options
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
  parser.add_argument("-l", "--log-file", help="Duplicate logs to specified file")

  # Subcommands
  subparsers = parser.add_subparsers(dest="command", help="Available commands")

  # Install command
  install_parser = subparsers.add_parser("install", help="Install the MCP server in Claude Desktop")
  install_parser.add_argument("-n", "--name", help="Server name in Claude Desktop (default: git project name)")
  install_parser.add_argument("-e", "--env", action="append", help="Environment variables (format: KEY=VALUE)")
  install_parser.add_argument(
    "--dev", action="store_true", help="Install in development mode with verbose logging to .cache/mcp.log"
  )

  # Run command
  run_parser = subparsers.add_parser("run", help="Run the MCP server")
  run_parser.add_argument("project_dir", help="Project directory to serve from")

  # Validate command
  _validate_parser = subparsers.add_parser("validate", help="Validate the MCP server syntax and configuration")

  args = parser.parse_args()

  # Configure logging based on arguments
  if args.log_file:
    add_file_logging(args.log_file)
    logger.info(f"Logging to file: {args.log_file}")

  # Set verbosity
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  # Execute command
  try:
    if args.command == "install":
      install_command(args)
    elif args.command == "validate":
      validate_command(args)
    elif args.command == "run":
      run_command(args)
    else:
      parser.print_help()
      sys.exit(1)
  except KeyboardInterrupt:
    logger.info("Interrupted by user")
    sys.exit(130)  # Standard exit code for SIGINT
  except Exception as e:
    logger.error(f"{type(e).__name__}: {e}")
    if args.verbose:
      logger.exception("Full traceback:")
    sys.exit(1)


if __name__ == "__main__":
  sys.exit(main())
