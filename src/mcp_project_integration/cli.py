"""CLI commands for MCP Project Integration"""

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

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

  # Ensure module is installed in venv via symlink
  module_name = "mcp_project_integration"
  module_source = project_root / "src" / module_name

  if not module_source.is_dir() or not (module_source / "__init__.py").exists():
    raise FileNotFoundError(
      f"Module not found at expected location: {module_source}\nEnsure your module exists under src/"
    )

  # Find site-packages in venv
  if sys.platform == "win32":
    site_packages = venv_path / "Lib" / "site-packages"
  else:
    # Find the correct Python version directory
    python_dirs = list((venv_path / "lib").glob("python*"))
    if not python_dirs:
      raise FileNotFoundError(f"No Python installation found in venv: {venv_path}")
    site_packages = python_dirs[0] / "site-packages"

  # Create symlink if it doesn't exist
  symlink_target = site_packages / module_name
  if not symlink_target.exists():
    try:
      symlink_target.symlink_to(module_source)
      logger.info(f"Created module symlink: {symlink_target} -> {module_source}")
    except OSError as e:
      logger.warning(f"Failed to create symlink: {e}")
      logger.info("Consider running: pip install -e . in your project root")
  elif symlink_target.is_symlink():
    logger.info(f"Module symlink exists: {symlink_target} -> {symlink_target.resolve()}")

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

  # Configure the server entry
  server_name = args.name or git_project_name

  # Determine Python executable path based on platform
  if sys.platform == "win32":
    python_executable = project_root / ".venv" / "Scripts" / "python.exe"
  else:
    python_executable = project_root / ".venv" / "bin" / "python"

  # Build command arguments using dictionary approach
  opts = {}

  # Module invocation (fixed prefix)
  opts["module"] = ["-m", "mcp_project_integration"]

  # Development mode global flags
  if args.dev:
    log_file_path = project_root / ".cache" / "mcp.log"
    opts["verbose"] = ["-v"]
    opts["log_file"] = ["-l", str(log_file_path)]
    logger.info(f"Development logs will be written to: {log_file_path}")

  # Subcommand
  opts["command"] = "claude-desktop"

  # Positional argument
  opts["cwd"] = str(project_root)

  # Optional flags
  if args.venv:
    opts["venv"] = ["--venv", args.venv]

  if args.src:
    opts["src"] = ["--src", args.src]

  # Pass environment variables as CLI arguments
  if args.env:
    for env_var in args.env:
      opts.setdefault("env", []).extend(["--env", env_var])

  # Define argument order
  arg_order = [
    "module",  # -m mcp_project_integration
    "verbose",  # -v (global flag, before subcommand)
    "log_file",  # -l path (global flag, before subcommand)
    "command",  # claude-desktop
    "cwd",  # positional: project root
    "venv",  # --venv path
    "src",  # --src path
    "env",  # --env KEY=VALUE (can be repeated)
  ]

  # Convert dictionary to argument list
  server_args = []
  for key in arg_order:
    val = opts.get(key)
    if val is None:
      continue
    if isinstance(val, str):
      server_args.append(val)
    else:
      server_args.extend(val)

  # Configure server entry (Claude Desktop only supports command and args)
  server_config = {"command": str(python_executable), "args": server_args}

  config["mcpServers"][server_name] = server_config

  # Write updated config
  with open(config_file, "w") as f:
    json.dump(config, f, indent=2)

  logger.info(f"Successfully installed server '{server_name}' in Claude Desktop")
  logger.info(f"Using Python from: {server_config['command']}")
  logger.info(f"Working directory: {project_root}")
  logger.info(f"Git project: {git_project_name}")


def claude_desktop_command(args) -> NoReturn:
  """Setup Python environment for Claude Desktop and exec run command"""
  logger.info("Claude Desktop environment setup")

  # 1. Change to specified working directory
  os.chdir(args.cwd)
  logger.info(f"Changed to working directory: {args.cwd}")

  # 2. Verify git repository
  try:
    git_root = find_git_root()
    logger.info(f"Verified git repository at: {git_root}")
  except subprocess.CalledProcessError:
    logger.error("Not in a git repository")
    sys.exit(1)

  # 3. Setup Python virtual environment
  venv_path = Path(args.venv) if args.venv else git_root / ".venv"
  if not venv_path.exists():
    logger.error(f"Virtual environment not found: {venv_path}")
    sys.exit(1)

  # Determine Python executable in venv
  if sys.platform == "win32":
    python_exe = venv_path / "Scripts" / "python.exe"
  else:
    python_exe = venv_path / "bin" / "python"

  if not python_exe.exists():
    logger.error(f"Python executable not found in venv: {python_exe}")
    sys.exit(1)

  logger.info(f"Using Python from: {python_exe}")

  # 4. Configure PYTHONPATH
  env = os.environ.copy()
  src_path = Path(args.src) if args.src else git_root / "src"

  if src_path.exists():
    pythonpath_entries = [str(src_path)]
    if env.get("PYTHONPATH"):
      pythonpath_entries.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
    logger.info(f"Added to PYTHONPATH: {src_path}")

  # 5. Apply custom environment variables
  if args.env:
    for env_var in args.env:
      key, value = env_var.split("=", 1)
      env[key] = value
      logger.info(f"Set environment variable: {key}")

  # 6. Build run command using dictionary approach
  opts = {}

  # Global options (must come before subcommand)
  if args.verbose:
    opts["verbose"] = ["-v"]

  if args.log_file:
    opts["log_file"] = ["-l", args.log_file]

  # Subcommand
  opts["command"] = "run"

  # Define argument order
  arg_order = ["verbose", "log_file", "command"]

  # Convert dictionary to argument list
  run_args = [str(python_exe), "-m", "mcp_project_integration"]

  for key in arg_order:
    val = opts.get(key)
    if val is None:
      continue
    if isinstance(val, str):
      run_args.append(val)
    else:
      run_args.extend(val)

  # 7. Replace process with configured environment
  logger.info(f"Executing: {' '.join(run_args)}")
  logger.info("=" * 60)

  # Use execve to replace current process completely
  os.execve(str(python_exe), run_args, env)
  assert False, NoReturn


def run_command(args):
  """Run the MCP server - no setup, just execution"""
  logger.info("Starting MCP server")
  logger.info(f"Server name: {mcp.name}")
  logger.info(f"Working directory: {os.getcwd()}")
  logger.info(f"Python: {sys.executable}")

  # Verify we're in a git repository
  try:
    git_root = find_git_root()
    logger.info(f"Git project root: {git_root}")
    git_name = get_git_project_name()
    logger.info(f"Git project name: {git_name}")
  except subprocess.CalledProcessError:
    raise RuntimeError(f"Directory is not a git repository: {os.getcwd()}")

  # Run with stdio transport
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

  # Global options (available to all subcommands)
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
  parser.add_argument("-l", "--log-file", help="Duplicate logs to specified file")

  # Subcommands
  subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

  # Install command
  install_parser = subparsers.add_parser("install", help="Install the MCP server in Claude Desktop")
  install_parser.add_argument("-n", "--name", help="Server name in Claude Desktop (default: git project name)")
  install_parser.add_argument("-e", "--env", action="append", help="Environment variables (format: KEY=VALUE)")
  install_parser.add_argument(
    "--dev", action="store_true", help="Install in development mode with verbose logging to .cache/mcp.log"
  )
  install_parser.add_argument("--venv", help="Custom virtual environment path")
  install_parser.add_argument("--src", help="Custom source directory for PYTHONPATH")

  # Claude Desktop command
  claude_parser = subparsers.add_parser("claude-desktop", help="Setup Python environment and exec run command")
  claude_parser.add_argument("cwd", help="Working directory (project root)")
  claude_parser.add_argument("--venv", help="Virtual environment path (default: .venv)")
  claude_parser.add_argument("--src", help="Source directory to add to PYTHONPATH (default: src)")
  claude_parser.add_argument("-e", "--env", action="append", help="Environment variables to set (format: KEY=VALUE)")

  # Run command
  _run_parser = subparsers.add_parser("run", help="Run the MCP server")

  # Validate command
  _validate_parser = subparsers.add_parser("validate", help="Validate the MCP server syntax and configuration")

  # Parse arguments
  args = parser.parse_args()

  # Configure logging based on global arguments
  # This happens before subcommand execution
  if args.log_file:
    add_file_logging(args.log_file)
    logger.info(f"Logging to file: {args.log_file}")

  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

  # Execute appropriate command
  try:
    if args.command == "install":
      install_command(args)
    elif args.command == "claude-desktop":
      claude_desktop_command(args)
    elif args.command == "run":
      run_command(args)
    elif args.command == "validate":
      validate_command(args)
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
