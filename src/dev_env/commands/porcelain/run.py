"""Run command - execute a command in the current context."""

import json
import sys
from typing import Optional

from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand
from dev_env.commands.plumbing.exec import ExecCommand


class RunCommand:
  """Execute a command in the current development environment."""

  def execute(self, args):
    """Execute the run command."""
    # Resolve context
    context = self._resolve_context()

    if not context:
      print("Error: No context found", file=sys.stderr)
      print("Run this command from a project directory with an active environment", file=sys.stderr)
      sys.exit(1)

    # Check status
    status = self._get_status(context)
    if status["state"] == "notfound":
      print(f"Error: Environment '{context['name']}' does not exist", file=sys.stderr)
      print("Run 'dev-env work' to create it", file=sys.stderr)
      sys.exit(1)

    if status["state"] == "stopped":
      print(f"Error: Environment '{context['name']}' is stopped", file=sys.stderr)
      print("Run 'dev-env work' to start it", file=sys.stderr)
      sys.exit(1)

    # Execute command
    command = getattr(args, "command", [])
    if not command:
      print("Error: No command specified", file=sys.stderr)
      sys.exit(1)

    self._execute_command(context, command)

  def _resolve_context(self) -> Optional[dict]:
    """Resolve context from current directory."""
    resolve_args = type("Args", (), {"name": None})()
    result = self._run_plumbing_command(ContextResolveCommand(), resolve_args)

    if "error" not in result:
      return result
    return None

  def _get_status(self, context: dict) -> dict:
    """Get environment status."""
    status_args = type("Args", (), {"context": context["name"]})()
    return self._run_plumbing_command(EnvStatusCommand(), status_args)

  def _execute_command(self, context: dict, command: list):
    """Execute command in the environment."""
    exec_args = type("Args", (), {"context": context["name"], "command": command})()
    result = self._run_plumbing_command(ExecCommand(), exec_args)

    if "error" in result:
      print(f"Error executing command: {result['error']}", file=sys.stderr)
      sys.exit(1)

    # Print command output
    if "output" in result:
      print(result["output"], end="")

    # Exit with the same code as the command
    exit_code = result.get("exit_code", 0)
    if exit_code != 0:
      sys.exit(exit_code)

  def _run_plumbing_command(self, command, args) -> dict:
    """Run a plumbing command and return the result."""
    import io
    from contextlib import redirect_stdout

    output = io.StringIO()
    with redirect_stdout(output):
      try:
        command.run(args)
      except SystemExit:
        pass

    try:
      return json.loads(output.getvalue())
    except json.JSONDecodeError:
      return {"error": "Failed to parse command output"}
