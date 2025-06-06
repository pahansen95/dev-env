"""Shell command - open an interactive shell in the environment."""

import json
from typing import Optional, Any

from dev_env.base_command import BaseCommand
from dev_env.utils import ContextNotFoundError, DevEnvError
from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand
from dev_env.commands.plumbing.attach import AttachCommand


class ShellCommand(BaseCommand):
  """Open an interactive shell in the development environment."""

  def _run(self, args: Any) -> None:
    """Execute the shell command logic."""
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

  def _attach_to_environment(self, context: dict) -> None:
    """Attach to the environment's TTY."""
    print(f"Entering environment '{context['name']}'...")
    print("Press Ctrl-D or type 'exit' to leave the environment")
    print()

    # The attach command is special - it takes over the TTY
    # So we need to call it directly instead of capturing output
    attach_args = type("Args", (), {"context": context["name"]})()
    attach_cmd = AttachCommand()

    # This will take over the TTY until the user detaches
    try:
      attach_cmd.execute(attach_args)
    except Exception as e:
      raise DevEnvError(f"Failed to attach to environment: {e}")

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
