"""Simple CLI main function tests for coverage improvement"""

import pytest
from unittest.mock import patch, MagicMock

from dev_env.cli import main


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
  @patch("dev_env.commands.porcelain.status.StatusCommand")
  def test_main_dispatches_status_command(self, mock_status_class):
    """Test main function dispatches to status command"""
    mock_status = MagicMock()
    mock_status_class.return_value = mock_status

    result = main()

    assert result == 0
    mock_status_class.assert_called_once()
    mock_status.execute.assert_called_once()

  @patch("sys.argv", ["dev-env", "work"])
  @patch("dev_env.commands.porcelain.work.WorkCommand")
  def test_main_dispatches_work_command(self, mock_work_class):
    """Test main function dispatches to work command"""
    mock_work = MagicMock()
    mock_work_class.return_value = mock_work

    result = main()

    assert result == 0
    mock_work_class.assert_called_once()
    mock_work.execute.assert_called_once()

  @patch("sys.argv", ["dev-env", "stop"])
  @patch("dev_env.commands.porcelain.stop.StopCommand")
  def test_main_dispatches_stop_command(self, mock_stop_class):
    """Test main function dispatches to stop command"""
    mock_stop = MagicMock()
    mock_stop_class.return_value = mock_stop

    result = main()

    assert result == 0
    mock_stop_class.assert_called_once()
    mock_stop.execute.assert_called_once()

  @patch("sys.argv", ["dev-env", "work"])
  @patch("dev_env.commands.porcelain.work.WorkCommand")
  def test_main_handles_dev_env_error(self, mock_work_class, capsys):
    """Test main function handles DevEnvError"""
    from dev_env.utils import DevEnvError

    error = DevEnvError("Test error")
    error.exit_code = 5
    mock_work = MagicMock()
    mock_work.execute.side_effect = error
    mock_work_class.return_value = mock_work

    result = main()

    assert result == 5
    captured = capsys.readouterr()
    assert "Test error" in captured.err

  @patch("dev_env.commands.porcelain.work.WorkCommand")
  def test_main_creates_state_directory(self, mock_work_class, tmp_path):
    """Test main function creates state directory"""
    state_dir = tmp_path / "test-state"
    mock_work = MagicMock()
    mock_work_class.return_value = mock_work

    with patch("sys.argv", ["dev-env", "--state-dir", str(state_dir), "work"]):
      result = main()

    assert result == 0
    assert state_dir.exists()


class TestArgumentParsing:
  """Test argument parsing coverage"""

  @patch("sys.argv", ["dev-env", "work", "--name", "custom-context"])
  @patch("dev_env.commands.porcelain.work.WorkCommand")
  def test_main_work_with_name_override(self, mock_work_class):
    """Test work command with name override"""
    mock_work = MagicMock()
    mock_work_class.return_value = mock_work

    result = main()

    assert result == 0
    args = mock_work.execute.call_args[0][0]
    assert args.name == "custom-context"

  @patch("sys.argv", ["dev-env", "stop", "--name", "test-context"])
  @patch("dev_env.commands.porcelain.stop.StopCommand")
  def test_main_stop_with_name_flag(self, mock_stop_class):
    """Test stop command with name flag"""
    mock_stop = MagicMock()
    mock_stop_class.return_value = mock_stop

    result = main()

    assert result == 0
    args = mock_stop.execute.call_args[0][0]
    assert args.name == "test-context"

  @patch("sys.argv", ["dev-env", "run", "bash", "-c", "echo hello"])
  @patch("dev_env.commands.porcelain.run.RunCommand")
  def test_main_run_with_command(self, mock_run_class):
    """Test run command with command arguments"""
    mock_run = MagicMock()
    mock_run_class.return_value = mock_run

    result = main()

    assert result == 0
    args = mock_run.execute.call_args[0][0]
    assert args.command == ["bash", "-c", "echo hello"]

  @patch("sys.argv", ["dev-env", "status", "--all"])
  @patch("dev_env.commands.porcelain.status.StatusCommand")
  def test_main_status_with_all_flag(self, mock_status_class):
    """Test status command with --all flag"""
    mock_status = MagicMock()
    mock_status_class.return_value = mock_status

    result = main()

    assert result == 0
    args = mock_status.execute.call_args[0][0]
    assert args.all is True

  @patch("sys.argv", ["dev-env", "shell"])
  @patch("dev_env.commands.porcelain.shell.ShellCommand")
  def test_main_shell_command(self, mock_shell_class):
    """Test shell command dispatch"""
    mock_shell = MagicMock()
    mock_shell_class.return_value = mock_shell

    result = main()

    assert result == 0
    mock_shell_class.assert_called_once()
    mock_shell.execute.assert_called_once()


class TestPlumbingCommands:
  """Test plumbing command dispatch"""

  @patch("sys.argv", ["dev-env", "context-create", "test-context"])
  @patch("dev_env.commands.plumbing.context_create.ContextCreateCommand")
  def test_main_context_create_command(self, mock_context_create_class):
    """Test context-create command dispatch"""
    mock_context_create = MagicMock()
    mock_context_create_class.return_value = mock_context_create

    result = main()

    assert result == 0
    mock_context_create_class.assert_called_once()
    mock_context_create.run.assert_called_once()

  @patch("sys.argv", ["dev-env", "env-status", "--context", "test-context"])
  @patch("dev_env.commands.plumbing.env_status.EnvStatusCommand")
  def test_main_env_status_command(self, mock_env_status_class):
    """Test env-status command dispatch"""
    mock_env_status = MagicMock()
    mock_env_status_class.return_value = mock_env_status

    result = main()

    assert result == 0
    args = mock_env_status.run.call_args[0][0]
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
    result = main()

    assert result == 1
    captured = capsys.readouterr()
    assert "Unknown command: unknown-command" in captured.err
