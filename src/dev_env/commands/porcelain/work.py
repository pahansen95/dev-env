"""Work command - start or resume a development session."""

import json
import sys
from pathlib import Path
from typing import Optional

from dev_env.commands.plumbing.context_create import ContextCreateCommand
from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.env_create import EnvCreateCommand
from dev_env.commands.plumbing.env_start import EnvStartCommand
from dev_env.commands.plumbing.env_status import EnvStatusCommand


class WorkCommand:
  """Start or resume a development session."""

  def execute(self, args):
    """Execute the work command."""
    # Step 1: Context resolution
    context = self._resolve_context(args.name if hasattr(args, "name") else None)
    if not context:
      context = self._create_context()

    # Step 2: Configuration
    config = self._load_config(context)
    if not config:
      config = self._setup_wizard(context)

    # Step 3: Environment management
    status = self._get_status(context)
    if status["state"] == "stopped":
      self._start_environment(context)
    elif status["state"] == "notfound":
      self._create_environment(context, config)

    # Step 4: User feedback
    self._show_ready_message(context)

  def _resolve_context(self, name: Optional[str]) -> Optional[dict]:
    """Resolve or find a context."""
    self._show_progress("Resolving context")

    # Try to resolve context
    resolve_args = type("Args", (), {"name": name})()
    result = self._run_plumbing_command(ContextResolveCommand(), resolve_args)

    if "error" not in result:
      self._show_progress("Resolving context", done=True)
      return result

    return None

  def _create_context(self) -> dict:
    """Create a new context interactively."""
    self._show_progress("Creating new context")

    # Get context name
    name = input("Enter context name: ").strip()
    if not name:
      print("Error: Context name cannot be empty", file=sys.stderr)
      sys.exit(1)

    # Use current directory
    path = Path.cwd()

    # Create context
    create_args = type("Args", (), {"name": name, "path": str(path)})()
    result = self._run_plumbing_command(ContextCreateCommand(), create_args)

    if "error" in result:
      print(f"Error creating context: {result['error']}", file=sys.stderr)
      sys.exit(1)

    self._show_progress("Creating new context", done=True)
    return result

  def _load_config(self, context: dict) -> Optional[dict]:
    """Load configuration from context path."""
    config_path = Path(context["path"]) / "dev-env.yaml"
    if config_path.exists():
      # Configuration exists
      return {"path": str(config_path)}
    return None

  def _setup_wizard(self, context: dict) -> dict:
    """Run setup wizard to create configuration."""
    self._show_progress("No configuration found - starting setup wizard")

    # Import here to avoid circular dependencies
    from dev_env.setup_wizard import SetupWizard
    from dev_env.context import Context

    # Convert dict to Context object for wizard
    context_obj = Context(
      id=context["id"],
      name=context["name"],
      path=Path(context["path"]),
      created_at=context.get("created_at", ""),
      last_used=context.get("last_used", ""),
      state=context.get("state", "active"),
    )

    # Run the wizard
    wizard = SetupWizard()
    config_data = wizard.run(context_obj)

    # Convert config to YAML format
    config_yaml = self._dict_to_yaml(config_data)

    config_path = Path(context["path"]) / "dev-env.yaml"
    config_path.write_text(config_yaml)

    self._show_progress("Configuration saved", done=True)
    return {"path": str(config_path)}

  def _get_status(self, context: dict) -> dict:
    """Get environment status."""
    self._show_progress("Checking environment status")

    status_args = type("Args", (), {"context": context["name"]})()
    result = self._run_plumbing_command(EnvStatusCommand(), status_args)

    self._show_progress("Checking environment status", done=True)
    return result

  def _start_environment(self, context: dict):
    """Start an existing environment."""
    self._show_progress("Starting environment")

    start_args = type("Args", (), {"context": context["name"]})()
    result = self._run_plumbing_command(EnvStartCommand(), start_args)

    if "error" in result:
      print(f"Error starting environment: {result['error']}", file=sys.stderr)
      sys.exit(1)

    self._show_progress("Starting environment", done=True)

  def _create_environment(self, context: dict, config: dict):
    """Create a new environment."""
    self._show_progress("Creating environment")

    create_args = type("Args", (), {"context": context["name"]})()
    result = self._run_plumbing_command(EnvCreateCommand(), create_args)

    if "error" in result:
      print(f"Error creating environment: {result['error']}", file=sys.stderr)
      sys.exit(1)

    self._show_progress("Creating environment", done=True)

    # Now start it
    self._start_environment(context)

  def _show_ready_message(self, context: dict):
    """Show ready message to user."""
    print(f"\n✓ Development environment '{context['name']}' is ready!")
    print(f"  Working directory: {context['path']}")
    print("\nTo enter the environment, run:")
    print("  dev-env shell")
    print("\nTo execute a command, run:")
    print("  dev-env run <command>")

  def _show_progress(self, message: str, done: bool = False):
    """Show progress message."""
    symbol = "✓" if done else "●"
    print(f"{symbol} {message}")

  def _run_plumbing_command(self, command, args) -> dict:
    """Run a plumbing command and return the result."""
    # Capture stdout
    import io
    from contextlib import redirect_stdout

    output = io.StringIO()
    with redirect_stdout(output):
      try:
        command.run(args)
      except SystemExit:
        # Plumbing commands exit on error
        pass

    # Parse JSON output
    try:
      return json.loads(output.getvalue())
    except json.JSONDecodeError:
      return {"error": "Failed to parse command output"}

  def _dict_to_yaml(self, data: dict) -> str:
    """Convert dictionary to YAML format without external dependencies."""
    lines = []
    lines.append("# Development Environment Configuration")

    def write_value(key: str, value: Any, indent: int = 0):
      """Recursively write YAML values."""
      prefix = "  " * indent

      if value is None:
        return
      elif isinstance(value, dict):
        lines.append(f"{prefix}{key}:")
        for k, v in value.items():
          write_value(k, v, indent + 1)
      elif isinstance(value, list):
        lines.append(f"{prefix}{key}:")
        for item in value:
          if isinstance(item, dict):
            lines.append(f"{prefix}  -")
            for k, v in item.items():
              write_value(k, v, indent + 2)
          else:
            lines.append(f"{prefix}  - {item}")
      elif isinstance(value, str):
        # Quote strings that might be interpreted as other types
        if value.lower() in ("true", "false", "yes", "no") or value.isdigit():
          lines.append(f'{prefix}{key}: "{value}"')
        else:
          lines.append(f"{prefix}{key}: {value}")
      else:
        lines.append(f"{prefix}{key}: {value}")

    for key, value in data.items():
      write_value(key, value)

    return "\n".join(lines)
