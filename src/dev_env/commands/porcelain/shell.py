"""Shell command - open an interactive shell in the environment."""

import json
import sys
from typing import Optional

from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand
from dev_env.commands.plumbing.attach import AttachCommand


class ShellCommand:
  """Open an interactive shell in the development environment."""

  def execute(self, args):
    """Execute the shell command."""
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

    # Attach to the environment
    self._attach_to_environment(context)

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

  def _attach_to_environment(self, context: dict):
    """Attach to the environment's TTY."""
    print(f"Entering environment '{context['name']}'...")
    print("Press Ctrl-D or type 'exit' to leave the environment")
    print()

    # The attach command is special - it takes over the TTY
    # So we need to call it directly instead of capturing output
    attach_args = type("Args", (), {"context": context["name"]})()
    attach_cmd = AttachCommand()

    # This will take over the TTY until the user detaches
    attach_cmd.execute(attach_args)

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
