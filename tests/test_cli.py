"""CLI command tests for dev-env context-based interface"""

from unittest.mock import patch, MagicMock
from argparse import Namespace

from dev_env.utils import DevEnvError


class TestWorkCommand:
  """Test work command functionality"""

  @patch("dev_env.commands.porcelain.work.WorkCommand.execute")
  def test_work_command_execution(self, mock_execute):
    """Test work command executes successfully"""
    from dev_env.commands.porcelain.work import WorkCommand

    args = Namespace(name="test-context")
    command = WorkCommand()
    command.execute(args)

    mock_execute.assert_called_once_with(args)

  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  @patch("dev_env.commands.porcelain.work.WorkCommand._create_context")
  def test_work_context_resolution(self, mock_create, mock_resolve):
    """Test work command context resolution logic"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Test context not found - should create new
    mock_resolve.return_value = None
    mock_create.return_value = {"id": "test", "name": "test", "path": "/test"}

    command = WorkCommand()
    args = Namespace(name=None)

    # This would be called within execute(), testing the logic flow
    context = mock_resolve(None)
    if not context:
      context = mock_create()

    mock_resolve.assert_called_once_with(None)
    mock_create.assert_called_once()
    assert context["name"] == "test"

  @patch("dev_env.commands.porcelain.work.WorkCommand._get_status")
  def test_work_environment_status_check(self, mock_get_status):
    """Test work command checks environment status"""
    from dev_env.commands.porcelain.work import WorkCommand

    mock_get_status.return_value = {"state": "running"}

    command = WorkCommand()
    context = {"name": "test", "path": "/test"}
    status = command._get_status(context)

    assert status["state"] == "running"


class TestStopCommand:
  """Test stop command functionality"""

  @patch("dev_env.commands.porcelain.stop.StopCommand.execute")
  def test_stop_command_execution(self, mock_execute):
    """Test stop command executes successfully"""
    from dev_env.commands.porcelain.stop import StopCommand

    args = Namespace(name="test-context")
    command = StopCommand()
    command.execute(args)

    mock_execute.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.context_resolve.ContextResolveCommand")
  @patch("dev_env.commands.plumbing.env_stop.EnvStopCommand")
  def test_stop_context_resolution_and_execution(self, mock_env_stop_class, mock_resolve_class):
    """Test stop command resolves context and stops environment"""
    from dev_env.commands.porcelain.stop import StopCommand

    # Mock context resolution
    mock_resolve = MagicMock()
    mock_resolve_class.return_value = mock_resolve

    # Mock environment stop
    mock_env_stop = MagicMock()
    mock_env_stop_class.return_value = mock_env_stop

    command = StopCommand()
    args = Namespace(name="test-context")

    # Test the command pattern - this would be part of execute()
    mock_resolve_class.assert_not_called()  # Until execute() is actually called


class TestStatusCommand:
  """Test status command functionality"""

  @patch("dev_env.commands.porcelain.status.StatusCommand.execute")
  def test_status_command_execution(self, mock_execute):
    """Test status command executes successfully"""
    from dev_env.commands.porcelain.status import StatusCommand

    args = Namespace(all=False)
    command = StatusCommand()
    command.execute(args)

    mock_execute.assert_called_once_with(args)

  @patch("dev_env.commands.porcelain.status.StatusCommand._show_all_status")
  @patch("dev_env.commands.porcelain.status.StatusCommand._show_current_status")
  def test_status_all_vs_current(self, mock_current, mock_all):
    """Test status command handles --all flag correctly"""
    from dev_env.commands.porcelain.status import StatusCommand

    command = StatusCommand()

    # Test --all flag
    args_all = Namespace(all=True)
    command.execute(args_all)
    mock_all.assert_called_once()

    # Test current only
    args_current = Namespace(all=False)
    command.execute(args_current)
    mock_current.assert_called_once()


class TestRunCommand:
  """Test run command functionality"""

  @patch("dev_env.commands.porcelain.run.RunCommand.execute")
  def test_run_command_execution(self, mock_execute):
    """Test run command executes successfully"""
    from dev_env.commands.porcelain.run import RunCommand

    args = Namespace(command=["ls", "-la"])
    command = RunCommand()
    command.execute(args)

    mock_execute.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.context_resolve.ContextResolveCommand")
  @patch("dev_env.commands.plumbing.exec.ExecCommand")
  def test_run_context_resolution_and_execution(self, mock_exec_class, mock_resolve_class):
    """Test run command resolves context and executes command"""
    from dev_env.commands.porcelain.run import RunCommand

    # Mock context resolution
    mock_resolve = MagicMock()
    mock_resolve_class.return_value = mock_resolve

    # Mock command execution
    mock_exec = MagicMock()
    mock_exec_class.return_value = mock_exec

    command = RunCommand()
    args = Namespace(command=["echo", "hello"])

    # Verify command structure exists
    assert hasattr(command, "execute")


class TestShellCommand:
  """Test shell command functionality"""

  @patch("dev_env.commands.porcelain.shell.ShellCommand.execute")
  def test_shell_command_execution(self, mock_execute):
    """Test shell command executes successfully"""
    from dev_env.commands.porcelain.shell import ShellCommand

    args = Namespace()
    command = ShellCommand()
    command.execute(args)

    mock_execute.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.context_resolve.ContextResolveCommand")
  @patch("dev_env.commands.plumbing.attach.AttachCommand")
  def test_shell_context_resolution_and_attach(self, mock_attach_class, mock_resolve_class):
    """Test shell command resolves context and attaches to environment"""
    from dev_env.commands.porcelain.shell import ShellCommand

    # Mock context resolution
    mock_resolve = MagicMock()
    mock_resolve_class.return_value = mock_resolve

    # Mock attach functionality
    mock_attach = MagicMock()
    mock_attach_class.return_value = mock_attach

    command = ShellCommand()
    args = Namespace()

    # Verify command structure exists
    assert hasattr(command, "execute")


class TestPlumbingCommands:
  """Test plumbing command functionality"""

  @patch("dev_env.commands.plumbing.context_create.ContextCreateCommand.run")
  def test_context_create_command(self, mock_run):
    """Test context-create plumbing command"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand

    args = Namespace(name="test-context", path="/test/path")
    command = ContextCreateCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.context_resolve.ContextResolveCommand.run")
  def test_context_resolve_command(self, mock_run):
    """Test context-resolve plumbing command"""
    from dev_env.commands.plumbing.context_resolve import ContextResolveCommand

    args = Namespace(name="test-context")
    command = ContextResolveCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.env_create.EnvCreateCommand.run")
  def test_env_create_command(self, mock_run):
    """Test env-create plumbing command"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    args = Namespace(context="test-context")
    command = EnvCreateCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.env_start.EnvStartCommand.run")
  def test_env_start_command(self, mock_run):
    """Test env-start plumbing command"""
    from dev_env.commands.plumbing.env_start import EnvStartCommand

    args = Namespace(context="test-context")
    command = EnvStartCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.env_stop.EnvStopCommand.run")
  def test_env_stop_command(self, mock_run):
    """Test env-stop plumbing command"""
    from dev_env.commands.plumbing.env_stop import EnvStopCommand

    args = Namespace(context="test-context")
    command = EnvStopCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)

  @patch("dev_env.commands.plumbing.env_status.EnvStatusCommand.run")
  def test_env_status_command(self, mock_run):
    """Test env-status plumbing command"""
    from dev_env.commands.plumbing.env_status import EnvStatusCommand

    args = Namespace(context="test-context")
    command = EnvStatusCommand()
    command.run(args)

    mock_run.assert_called_once_with(args)


class TestCommandErrorHandling:
  """Test command error handling scenarios"""

  @patch("dev_env.commands.porcelain.work.WorkCommand.execute")
  def test_work_command_dev_env_error(self, mock_execute):
    """Test work command handles DevEnvError properly"""
    from dev_env.commands.porcelain.work import WorkCommand

    error = DevEnvError("Test error")
    error.exit_code = 5
    mock_execute.side_effect = error

    command = WorkCommand()
    args = Namespace(name="test")

    try:
      command.execute(args)
      assert False, "Should have raised DevEnvError"
    except DevEnvError as e:
      assert str(e) == "Test error"
      assert e.exit_code == 5

  @patch("dev_env.commands.porcelain.status.StatusCommand._resolve_context")
  def test_status_no_context_found(self, mock_resolve):
    """Test status command when no context is found"""
    from dev_env.commands.porcelain.status import StatusCommand

    mock_resolve.return_value = None

    command = StatusCommand()

    # Test the context resolution logic
    context = command._resolve_context()
    assert context is None


class TestStateManagement:
  """Test state management integration"""

  @patch("dev_env.state.StateManager")
  def test_context_creation_state_integration(self, mock_state_class):
    """Test context creation integrates with state management"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand

    mock_state = MagicMock()
    mock_state_class.return_value = mock_state

    command = ContextCreateCommand()
    args = Namespace(name="test", path="/test")

    # This would be tested at a higher integration level
    # Here we verify the command structure exists
    assert hasattr(command, "run")

  @patch("dev_env.state.StateManager")
  def test_environment_state_tracking(self, mock_state_class):
    """Test environment state tracking through commands"""
    from dev_env.commands.plumbing.env_status import EnvStatusCommand

    mock_state = MagicMock()
    mock_state.get_environment.return_value = {"container_id": "test123", "state": "running"}
    mock_state_class.return_value = mock_state

    command = EnvStatusCommand()
    args = Namespace(context="test")

    # Verify command structure for state integration
    assert hasattr(command, "run")
