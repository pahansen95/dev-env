"""Status command - show human-readable environment status."""

import json
from datetime import datetime
from typing import Optional

from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.context_list import ContextListCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand


class StatusCommand:
  """Show human-readable status of development environments."""

  def execute(self, args):
    """Execute the status command."""
    # Check if we want all contexts or current
    show_all = getattr(args, "all", False)

    if show_all:
      self._show_all_status()
    else:
      self._show_current_status()

  def _show_current_status(self):
    """Show status of current context."""
    # Resolve current context
    context = self._resolve_context()

    if not context:
      print("No context found in current directory")
      print("\nTo create a new environment, run:")
      print("  dev-env work")
      return

    # Get environment status
    status = self._get_status(context)

    # Display status
    self._display_context_status(context, status)

  def _show_all_status(self):
    """Show status of all contexts."""
    # List all contexts
    list_args = type("Args", (), {})()
    result = self._run_plumbing_command(ContextListCommand(), list_args)

    contexts = result.get("contexts", [])
    if not contexts:
      print("No development environments found")
      print("\nTo create a new environment, run:")
      print("  dev-env work")
      return

    print(f"Development Environments ({len(contexts)} total):\n")

    for context in contexts:
      # Get status for each
      status = self._get_status(context)
      self._display_context_summary(context, status)
      print()

  def _display_context_status(self, context: dict, status: dict):
    """Display detailed status for a single context."""
    print(f"Context: {context['name']}")
    print(f"Path: {context['path']}")
    print(f"ID: {context['id'][:12]}...")

    # Parse timestamps
    created = self._format_timestamp(context.get("created_at"))
    last_used = self._format_timestamp(context.get("last_used"))

    print(f"Created: {created}")
    print(f"Last used: {last_used}")

    # Environment status
    env_state = status.get("state", "notfound")
    state_symbol = {
      "running": "🟢",
      "stopped": "🟡",
      "notfound": "⚪",
    }.get(env_state, "❓")

    print(f"\nEnvironment: {state_symbol} {env_state}")

    if env_state != "notfound":
      container_id = status.get("container_id", "")[:12]
      print(f"Container: {container_id}")

      if "created_at" in status:
        env_created = self._format_timestamp(status["created_at"])
        print(f"Environment created: {env_created}")

    # Show commands
    print("\nAvailable commands:")
    if env_state == "notfound":
      print("  dev-env work      # Create and start environment")
    elif env_state == "stopped":
      print("  dev-env work      # Start environment")
      print("  dev-env down      # Remove environment")
    else:
      print("  dev-env shell     # Enter interactive shell")
      print("  dev-env run       # Execute command")
      print("  dev-env stop      # Stop environment")

  def _display_context_summary(self, context: dict, status: dict):
    """Display summary status for a context."""
    env_state = status.get("state", "notfound")
    state_symbol = {
      "running": "🟢",
      "stopped": "🟡",
      "notfound": "⚪",
    }.get(env_state, "❓")

    print(f"{state_symbol} {context['name']}")
    print(f"   Path: {context['path']}")
    print(f"   State: {env_state}")

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

  def _format_timestamp(self, timestamp: Optional[str]) -> str:
    """Format ISO timestamp to human-readable."""
    if not timestamp:
      return "Unknown"

    try:
      dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
      now = datetime.now(dt.tzinfo)
      delta = now - dt

      if delta.days > 7:
        return dt.strftime("%Y-%m-%d")
      elif delta.days > 0:
        return f"{delta.days} days ago"
      elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hours ago"
      elif delta.seconds > 60:
        minutes = delta.seconds // 60
        return f"{minutes} minutes ago"
      else:
        return "Just now"
    except:
      return timestamp

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
