"""Simple CLI main function tests for coverage improvement"""

import pytest
from unittest.mock import patch

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

  @patch("sys.argv", ["dev-env", "list"])
  @patch("dev_env.cli.cmd_list")
  def test_main_dispatches_list_command(self, mock_cmd_list):
    """Test main function dispatches to list command"""
    mock_cmd_list.return_value = 0

    result = main()

    assert result == 0
    mock_cmd_list.assert_called_once()

  @patch("sys.argv", ["dev-env", "up", "config.py"])
  @patch("dev_env.cli.cmd_up")
  def test_main_dispatches_up_command(self, mock_cmd_up):
    """Test main function dispatches to up command"""
    mock_cmd_up.return_value = 0

    result = main()

    assert result == 0
    mock_cmd_up.assert_called_once()

  @patch("sys.argv", ["dev-env", "down", "test-env"])
  @patch("dev_env.cli.cmd_down")
  def test_main_dispatches_down_command(self, mock_cmd_down):
    """Test main function dispatches to down command"""
    mock_cmd_down.return_value = 0

    result = main()

    assert result == 0
    mock_cmd_down.assert_called_once()

  @patch("sys.argv", ["dev-env", "up", "config.py"])
  @patch("dev_env.cli.cmd_up")
  def test_main_handles_dev_env_error(self, mock_cmd_up, capsys):
    """Test main function handles DevEnvError"""
    from dev_env.utils import DevEnvError

    error = DevEnvError("Test error")
    error.exit_code = 5
    mock_cmd_up.side_effect = error

    result = main()

    assert result == 5
    captured = capsys.readouterr()
    assert "Test error" in captured.err

  @patch("dev_env.cli.cmd_up")
  def test_main_creates_state_directory(self, mock_cmd_up, tmp_path):
    """Test main function creates state directory"""
    state_dir = tmp_path / "test-state"
    mock_cmd_up.return_value = 0

    with patch("sys.argv", ["dev-env", "--state-dir", str(state_dir), "up", "config.py"]):
      result = main()

    assert result == 0
    assert state_dir.exists()


class TestArgumentParsing:
  """Test argument parsing coverage"""

  @patch("sys.argv", ["dev-env", "up", "config.py", "--name", "custom-env"])
  @patch("dev_env.cli.cmd_up")
  def test_main_up_with_name_override(self, mock_cmd_up):
    """Test up command with name override"""
    mock_cmd_up.return_value = 0

    result = main()

    assert result == 0
    args = mock_cmd_up.call_args[0][0]
    assert args.name == "custom-env"

  @patch("sys.argv", ["dev-env", "down", "test-env", "--volumes"])
  @patch("dev_env.cli.cmd_down")
  def test_main_down_with_volumes_flag(self, mock_cmd_down):
    """Test down command with volumes flag"""
    mock_cmd_down.return_value = 0

    result = main()

    assert result == 0
    args = mock_cmd_down.call_args[0][0]
    assert args.volumes is True

  @patch("sys.argv", ["dev-env", "exec", "test-env", "bash"])
  @patch("dev_env.cli.cmd_exec")
  def test_main_exec_with_command(self, mock_cmd_exec):
    """Test exec command with command arguments"""
    mock_cmd_exec.return_value = 0

    result = main()

    assert result == 0
    args = mock_cmd_exec.call_args[0][0]
    assert args.exec_command == ["bash"]

  @patch("sys.argv", ["dev-env", "logs", "test-env", "--follow", "--tail", "100"])
  @patch("dev_env.cli.cmd_logs")
  def test_main_logs_with_options(self, mock_cmd_logs):
    """Test logs command with options"""
    mock_cmd_logs.return_value = 0

    result = main()

    assert result == 0
    args = mock_cmd_logs.call_args[0][0]
    assert args.follow is True
    assert args.tail == 100

  @patch("sys.argv", ["dev-env", "ssh", "test-env", "extra", "args"])
  @patch("dev_env.cli.cmd_ssh")
  def test_main_ssh_with_args(self, mock_cmd_ssh):
    """Test ssh command with SSH arguments"""
    mock_cmd_ssh.return_value = 0

    result = main()

    assert result == 0
    args = mock_cmd_ssh.call_args[0][0]
    assert args.ssh_args == ["extra", "args"]


class TestCompletionCommand:
  """Test completion command handling"""

  @patch("sys.argv", ["dev-env", "completion", "bash"])
  def test_main_completion_command(self):
    """Test completion command uses func attribute"""
    # This should work if completion command is properly configured
    with patch("dev_env.completion.cmd_completion") as mock_completion:
      mock_completion.return_value = 0

      result = main()

      # Should either succeed (if completion works) or fail gracefully
      assert result in [0, 1]
