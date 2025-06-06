"""Simple CLI main function tests for coverage improvement"""

import pytest
from unittest.mock import patch, MagicMock

from dev_env.cli import main, set_command_factory, CommandFactory
from dev_env.io import MockInputProvider


class TestMainFunctionBasic:
  """Test main function coverage"""

  @patch("sys.argv", ["dev-env"])
  def test_main_no_command(self, capsys):
    """Test main function when no command is provided"""
    result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower() or "help" in captured.out.lower()

  @patch("sys.argv", ["dev-env", "--version"])
  def test_main_version_flag(self):
    """Test main function with --version flag"""
    with pytest.raises(SystemExit):
      main()

  @patch("sys.argv", ["dev-env", "status", "--all"])
  def test_main_dispatches_status_command(self):
    """Test main function dispatches to status command"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_status = MagicMock()
    mock_status.execute.return_value = 0  # Return success exit code
    mock_factory.create_status_command.return_value = mock_status

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      mock_factory.create_status_command.assert_called_once()
      mock_status.execute.assert_called_once()
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "work"])
  def test_main_dispatches_work_command(self):
    """Test main function dispatches to work command"""
    # Create factory with mock input provider to avoid stdin issues
    mock_input_provider = MockInputProvider(["test-context"])
    test_factory = CommandFactory(input_provider=mock_input_provider)

    # Mock the work command to avoid actual execution
    mock_work = MagicMock()
    mock_work.execute.return_value = 0  # Return success exit code
    with patch.object(test_factory, "create_work_command", return_value=mock_work):
      original_factory = CommandFactory()
      set_command_factory(test_factory)

      try:
        result = main()

        assert result == 0
        mock_work.execute.assert_called_once()
      finally:
        # Restore original factory
        set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "stop"])
  def test_main_dispatches_stop_command(self):
    """Test main function dispatches to stop command"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_stop = MagicMock()
    mock_stop.execute.return_value = 0  # Return success exit code
    mock_factory.create_stop_command.return_value = mock_stop

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      mock_factory.create_stop_command.assert_called_once()
      mock_stop.execute.assert_called_once()
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "work"])
  def test_main_handles_dev_env_error(self, capsys):
    """Test main function handles DevEnvError"""
    from dev_env.utils import DevEnvError

    error = DevEnvError("Test error")
    error.exit_code = 5

    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_work = MagicMock()
    mock_work.execute.side_effect = error
    mock_factory.create_work_command.return_value = mock_work

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 5
      captured = capsys.readouterr()
      assert "Test error" in captured.err
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  def test_main_creates_state_directory(self, tmp_path):
    """Test main function creates state directory"""
    state_dir = tmp_path / "test-state"

    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_work = MagicMock()
    mock_work.execute.return_value = 0  # Return success exit code
    mock_factory.create_work_command.return_value = mock_work

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      with patch("sys.argv", ["dev-env", "--state-dir", str(state_dir), "work"]):
        result = main()

      assert result == 0
      assert state_dir.exists()
    finally:
      # Restore original factory
      set_command_factory(original_factory)


class TestArgumentParsing:
  """Test argument parsing coverage"""

  @patch("sys.argv", ["dev-env", "work", "--name", "custom-context"])
  def test_main_work_with_name_override(self):
    """Test work command with name override"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_work = MagicMock()
    mock_work.execute.return_value = 0  # Return success exit code
    mock_factory.create_work_command.return_value = mock_work

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      args = mock_work.execute.call_args[0][0]
      assert args.name == "custom-context"
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "stop", "--name", "test-context"])
  def test_main_stop_with_name_flag(self):
    """Test stop command with name flag"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_stop = MagicMock()
    mock_stop.execute.return_value = 0  # Return success exit code
    mock_factory.create_stop_command.return_value = mock_stop

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      args = mock_stop.execute.call_args[0][0]
      assert args.name == "test-context"
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "run", "--", "bash", "-c", "echo hello"])
  def test_main_run_with_command(self):
    """Test run command with command arguments"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_run = MagicMock()
    mock_run.execute.return_value = 0  # Return success exit code
    mock_factory.create_run_command.return_value = mock_run

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      args = mock_run.execute.call_args[0][0]
      assert args.command == ["bash", "-c", "echo hello"]
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "status", "--all"])
  def test_main_status_with_all_flag(self):
    """Test status command with --all flag"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_status = MagicMock()
    mock_status.execute.return_value = 0  # Return success exit code
    mock_factory.create_status_command.return_value = mock_status

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      args = mock_status.execute.call_args[0][0]
      assert args.all is True
    finally:
      # Restore original factory
      set_command_factory(original_factory)

  @patch("sys.argv", ["dev-env", "shell"])
  def test_main_shell_command(self):
    """Test shell command dispatch"""
    # Create mock factory
    mock_factory = MagicMock(spec=CommandFactory)
    mock_shell = MagicMock()
    mock_shell.execute.return_value = 0  # Return success exit code
    mock_factory.create_shell_command.return_value = mock_shell

    # Set the factory for this test
    original_factory = CommandFactory()
    set_command_factory(mock_factory)

    try:
      result = main()

      assert result == 0
      mock_factory.create_shell_command.assert_called_once()
      mock_shell.execute.assert_called_once()
    finally:
      # Restore original factory
      set_command_factory(original_factory)


class TestPlumbingCommands:
  """Test plumbing command dispatch"""

  @patch("sys.argv", ["dev-env", "context-create", "test-context", "--path", "/tmp/test"])
  @patch("dev_env.cli.ContextCreateCommand")
  def test_main_context_create_command(self, mock_context_class):
    """Test context-create command dispatch"""
    # Create a mock instance
    mock_instance = MagicMock()
    mock_instance.run.return_value = None
    mock_context_class.return_value = mock_instance

    result = main()

    assert result == 0
    mock_context_class.assert_called_once()
    mock_instance.run.assert_called_once()

  @patch("sys.argv", ["dev-env", "env-status", "--context", "test-context"])
  @patch("dev_env.cli.EnvStatusCommand")
  def test_main_env_status_command(self, mock_env_status_class):
    """Test env-status command dispatch"""
    mock_instance = MagicMock()
    mock_instance.run.return_value = None
    mock_env_status_class.return_value = mock_instance

    result = main()

    assert result == 0
    mock_instance.run.assert_called_once()
    args = mock_instance.run.call_args[0][0]
    assert args.context == "test-context"


class TestCompletionCommand:
  """Test completion command handling"""

  @patch("sys.argv", ["dev-env", "completion", "bash"])
  def test_main_completion_command(self):
    """Test completion command uses func attribute"""
    with patch("dev_env.completion.cmd_completion") as mock_completion:
      mock_completion.return_value = 0

      result = main()

      assert result == 0
      mock_completion.assert_called_once()


class TestUnknownCommand:
  """Test unknown command handling"""

  @patch("sys.argv", ["dev-env", "unknown-command"])
  def test_main_unknown_command(self, capsys):
    """Test main function handles unknown commands"""
    with pytest.raises(SystemExit) as exc_info:
      main()

    assert exc_info.value.code == 2  # argparse returns 2 for invalid arguments
    captured = capsys.readouterr()
    assert "invalid choice: 'unknown-command'" in captured.err
