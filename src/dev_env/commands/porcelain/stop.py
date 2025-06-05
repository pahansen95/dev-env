"""Stop command - suspend a development environment."""

import json
import sys
from typing import Optional

from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_stop import EnvStopCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand


class StopCommand:
  """Stop a running development environment."""

  def execute(self, args):
    """Execute the stop command."""
    # Resolve context
    context_name = getattr(args, "name", None)
    context = self._resolve_context(context_name)

    if not context:
      print("Error: No context found", file=sys.stderr)
      print("Run this command from a project directory or specify --name", file=sys.stderr)
      sys.exit(1)

    # Check status
    status = self._get_status(context)
    if status["state"] == "notfound":
      print(f"Environment '{context['name']}' does not exist", file=sys.stderr)
      sys.exit(1)

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

  def _stop_environment(self, context: dict):
    """Stop the environment."""
    print(f"● Stopping environment '{context['name']}'...")

    stop_args = type("Args", (), {"context": context["name"]})()
    result = self._run_plumbing_command(EnvStopCommand(), stop_args)

    if "error" in result:
      print(f"Error stopping environment: {result['error']}", file=sys.stderr)
      sys.exit(1)

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
      return {"error": "Failed to parse command output"}
