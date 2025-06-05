"""Command-line interface using argparse"""

import argparse
import sys
from pathlib import Path

from . import __version__
from .utils import DevEnvError
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

  # Porcelain command handlers
  porcelain_commands = {
    "work": lambda args: WorkCommand().execute(args),
    "stop": lambda args: StopCommand().execute(args),
    "run": lambda args: RunCommand().execute(args),
    "status": lambda args: StatusCommand().execute(args),
    "shell": lambda args: ShellCommand().execute(args),
  }

  # Plumbing command handlers
  plumbing_commands = {
    "context-create": lambda args: ContextCreateCommand().run(args),
    "context-resolve": lambda args: ContextResolveCommand().run(args),
    "context-list": lambda args: ContextListCommand().run(args),
    "env-create": lambda args: EnvCreateCommand().run(args),
    "env-start": lambda args: EnvStartCommand().run(args),
    "env-stop": lambda args: EnvStopCommand().run(args),
    "env-status": lambda args: EnvStatusCommand().run(args),
    "plumbing-exec": lambda args: ExecCommand().run(args),
    "plumbing-attach": lambda args: AttachCommand().run(args),
  }

  try:
    # Handle completion command specially since it uses a different pattern
    if hasattr(args, "func"):
      return args.func(args)

    # Check if it's a porcelain command
    if args.command in porcelain_commands:
      porcelain_commands[args.command](args)
      return 0

    # Check if it's a plumbing command
    if args.command in plumbing_commands:
      plumbing_commands[args.command](args)
      return 0

    # Unknown command
    print(f"Unknown command: {args.command}", file=sys.stderr)
    parser.print_help()
    return 1
  except DevEnvError as e:
    print(e.format_error(), file=sys.stderr)
    return e.exit_code


if __name__ == "__main__":
  sys.exit(main())
