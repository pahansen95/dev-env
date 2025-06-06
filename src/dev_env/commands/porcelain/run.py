"""Run command - execute a command in the current context."""

import json
from typing import Optional, Any

from dev_env.base_command import BaseCommand
from dev_env.utils import ContextNotFoundError, DevEnvError
from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand
from dev_env.commands.plumbing.exec import ExecCommand


class RunCommand(BaseCommand):
  """Execute a command in the current development environment."""

  def _run(self, args: Any) -> None:
    """Execute the run command logic."""
    # Resolve context
    context = self._resolve_context()

    if not context:
      raise ContextNotFoundError("current directory context")

    # Check status
    status = self._get_status(context)

    # Handle error responses that lack 'state' key
    if "error" in status or "state" not in status:
      error_msg = status.get("error", "Invalid status response format")
      raise DevEnvError(f"Failed to check environment status: {error_msg}")

    if status["state"] == "notfound":
      raise DevEnvError(f"Environment '{context['name']}' does not exist. Run 'dev-env work' to create it.")

    if status["state"] == "stopped":
      raise DevEnvError(f"Environment '{context['name']}' is stopped. Run 'dev-env work' to start it.")

    # Execute command
    command = getattr(args, "command", [])
    if not command:
      raise DevEnvError("No command specified")

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

  def _execute_command(self, context: dict, command: list) -> None:
    """Execute command in the environment."""
    exec_args = type("Args", (), {"context": context["name"], "command": command})()
    result = self._run_plumbing_command(ExecCommand(), exec_args)

    if "error" in result:
      raise DevEnvError(f"Command execution failed: {result['error']}")

    # Print command output
    if "output" in result:
      print(result["output"], end="")

    # Note: Unlike the original, we don't exit with the command's exit code
    # This allows the framework to handle exit codes consistently
    # If the command failed, it should be reported as an error

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
      return {"error": "Failed to parse command output", "state": "error"}
