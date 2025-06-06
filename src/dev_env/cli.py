"""Command-line interface using argparse"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .utils import DevEnvError
from .io import InputProvider, StdinInputProvider
from .commands.plumbing.context_create import ContextCreateCommand
from .commands.plumbing.context_resolve import ContextResolveCommand
from .commands.plumbing.context_list import ContextListCommand
from .commands.plumbing.env_create import EnvCreateCommand
from .commands.plumbing.env_start import EnvStartCommand
from .commands.plumbing.env_stop import EnvStopCommand
from .commands.plumbing.env_status import EnvStatusCommand
from .commands.plumbing.exec import ExecCommand
from .commands.plumbing.attach import AttachCommand
from .commands.porcelain.work import WorkCommand
from .commands.porcelain.stop import StopCommand
from .commands.porcelain.run import RunCommand
from .commands.porcelain.status import StatusCommand
from .commands.porcelain.shell import ShellCommand


class CommandFactory:
  """Factory for creating command instances with proper dependency injection."""

  def __init__(self, input_provider: Optional[InputProvider] = None):
    """Initialize command factory with optional input provider."""
    self.input_provider = input_provider or StdinInputProvider()

  def create_work_command(self) -> WorkCommand:
    """Create WorkCommand with input provider."""
    return WorkCommand(input_provider=self.input_provider)

  def create_stop_command(self) -> StopCommand:
    """Create StopCommand."""
    return StopCommand()

  def create_run_command(self) -> RunCommand:
    """Create RunCommand."""
    return RunCommand()

  def create_status_command(self) -> StatusCommand:
    """Create StatusCommand."""
    return StatusCommand()

  def create_shell_command(self) -> ShellCommand:
    """Create ShellCommand."""
    return ShellCommand()


# Global command factory - can be overridden for testing
_command_factory = CommandFactory()


def set_command_factory(factory: CommandFactory) -> None:
  """Set global command factory (primarily for testing)."""
  global _command_factory
  _command_factory = factory


def main():
  """Main CLI entry point"""
  parser = argparse.ArgumentParser(prog="dev-env", description="Zero-dependency development environment management")
  parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
  parser.add_argument(
    "--state-dir", type=Path, default=Path.home() / ".dev-env" / "state", help="Directory for storing environment state"
  )

  subparsers = parser.add_subparsers(dest="command", help="Available commands")

  # completion command
  from .completion import add_completion_parser

  add_completion_parser(subparsers)

  # Porcelain commands (new style)
  work_parser = subparsers.add_parser("work", help="Start or resume development session")
  work_parser.add_argument("--name", help="Context name (default: create or find)")

  stop_parser = subparsers.add_parser("stop", help="Stop development environment")
  stop_parser.add_argument("--name", help="Context name (default: current directory)")

  run_parser = subparsers.add_parser("run", help="Execute command in current environment")
  run_parser.add_argument("command", nargs="+", help="Command to execute")

  status_parser = subparsers.add_parser("status", help="Show environment status")
  status_parser.add_argument("--all", action="store_true", help="Show all environments")

  subparsers.add_parser("shell", help="Open interactive shell")

  # Plumbing commands
  context_create_parser = subparsers.add_parser("context-create", help="Create a new context")
  context_create_parser.add_argument("name", help="Context name")
  context_create_parser.add_argument("--path", help="Path to context (default: current directory)")

  context_resolve_parser = subparsers.add_parser("context-resolve", help="Resolve context from path or name")
  context_resolve_parser.add_argument("--name", help="Context name to resolve")

  subparsers.add_parser("context-list", help="List all contexts")

  env_create_parser = subparsers.add_parser("env-create", help="Create environment from config")
  env_create_parser.add_argument("--context", help="Context name (default: resolve from current directory)")

  env_start_parser = subparsers.add_parser("env-start", help="Start existing environment")
  env_start_parser.add_argument("--context", help="Context name (default: resolve from current directory)")

  env_stop_parser = subparsers.add_parser("env-stop", help="Stop running environment")
  env_stop_parser.add_argument("--context", help="Context name (default: resolve from current directory)")

  env_status_parser = subparsers.add_parser("env-status", help="Get environment status")
  env_status_parser.add_argument("--context", help="Context name (default: resolve from current directory)")

  plumbing_exec_parser = subparsers.add_parser("plumbing-exec", help="Execute command in environment")
  plumbing_exec_parser.add_argument("--context", help="Context name (default: resolve from current directory)")
  plumbing_exec_parser.add_argument("command", nargs="+", help="Command to execute")

  plumbing_attach_parser = subparsers.add_parser("plumbing-attach", help="Attach to environment TTY")
  plumbing_attach_parser.add_argument("--context", help="Context name (default: resolve from current directory)")

  args = parser.parse_args()

  if not args.command:
    parser.print_help()
    return 1

  # Ensure state directory exists
  args.state_dir.mkdir(parents=True, exist_ok=True)

  # Porcelain command handlers using factory
  porcelain_commands = {
    "work": _command_factory.create_work_command,
    "stop": _command_factory.create_stop_command,
    "run": _command_factory.create_run_command,
    "status": _command_factory.create_status_command,
    "shell": _command_factory.create_shell_command,
  }

  # Plumbing command handlers (no dependency injection needed)
  plumbing_commands = {
    "context-create": ContextCreateCommand,
    "context-resolve": ContextResolveCommand,
    "context-list": ContextListCommand,
    "env-create": EnvCreateCommand,
    "env-start": EnvStartCommand,
    "env-stop": EnvStopCommand,
    "env-status": EnvStatusCommand,
    "plumbing-exec": ExecCommand,
    "plumbing-attach": AttachCommand,
  }

  try:
    # Handle completion command specially since it uses a different pattern
    if hasattr(args, "func"):
      return args.func(args)

    # Special handling for run command where args.command is a list
    if isinstance(args.command, list):
      # The run command overwrites the subcommand name with its positional argument
      command_name = "run"
    else:
      command_name = args.command

    # Check if it's a porcelain command
    if command_name in porcelain_commands:
      command = porcelain_commands[command_name]()
      return command.execute(args)

    # Check if it's a plumbing command
    if command_name in plumbing_commands:
      command = plumbing_commands[command_name]()
      command.run(args)
      return 0

    # Unknown command
    print(f"Unknown command: {command_name}", file=sys.stderr)
    parser.print_help()
    return 1
  except DevEnvError as e:
    print(e.format_error(), file=sys.stderr)
    return e.exit_code


if __name__ == "__main__":
  sys.exit(main())
