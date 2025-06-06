"""Stop command - suspend a development environment."""

import json
from typing import Optional, Any

from dev_env.base_command import BaseCommand
from dev_env.utils import ContextNotFoundError, DevEnvError
from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_stop import EnvStopCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand


class StopCommand(BaseCommand):
  """Stop a running development environment."""

  def _run(self, args: Any) -> None:
    """Execute the stop command logic."""
    # Resolve context
    context_name = getattr(args, "name", None)
    context = self._resolve_context(context_name)

    if not context:
      raise ContextNotFoundError(context_name or "current directory")

    # Check status
    status = self._get_status(context)

    # Handle error responses that lack 'state' key
    if "error" in status or "state" not in status:
      error_msg = status.get("error", "Invalid status response format")
      raise DevEnvError(f"Failed to check environment status: {error_msg}")

    if status["state"] == "notfound":
      raise DevEnvError(f"Environment '{context['name']}' does not exist")

    if status["state"] == "stopped":
      print(f"Environment '{context['name']}' is already stopped")
      return

    # Stop the environment
    self._stop_environment(context)

  def _resolve_context(self, name: Optional[str]) -> Optional[dict]:
    """Resolve context by name or current directory."""
    resolve_args = type("Args", (), {"name": name})()
    result = self._run_plumbing_command(ContextResolveCommand(), resolve_args)

    if "error" not in result:
      return result
    return None

  def _get_status(self, context: dict) -> dict:
    """Get environment status."""
    status_args = type("Args", (), {"context": context["name"]})()
    return self._run_plumbing_command(EnvStatusCommand(), status_args)

  def _stop_environment(self, context: dict) -> None:
    """Stop the environment."""
    print(f"● Stopping environment '{context['name']}'...")

    stop_args = type("Args", (), {"context": context["name"]})()
    result = self._run_plumbing_command(EnvStopCommand(), stop_args)

    if "error" in result:
      raise DevEnvError(f"Failed to stop environment: {result['error']}")

    print(f"✓ Environment '{context['name']}' stopped")

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
