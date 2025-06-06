"""Tests for porcelain commands."""

from unittest.mock import patch
from argparse import Namespace

from dev_env.commands.porcelain.work import WorkCommand
from dev_env.commands.porcelain.stop import StopCommand
from dev_env.commands.porcelain.run import RunCommand
from dev_env.commands.porcelain.status import StatusCommand
from dev_env.commands.porcelain.shell import ShellCommand


class TestWorkCommand:
  """Test work command functionality."""

  @patch("builtins.input", return_value="test-project")
  @patch("pathlib.Path.cwd")
  def test_work_creates_new_context(self, mock_cwd, mock_input, tmp_path, capsys):
    """Test work command creates new context when none exists."""
    mock_cwd.return_value = tmp_path

    # Mock plumbing commands
    with patch.object(WorkCommand, "_load_config", return_value={"base_image": "ubuntu:22.04"}):
      with patch.object(WorkCommand, "_run_plumbing_command") as mock_run:
        # First resolve returns error (no context)
        mock_run.side_effect = [
          {"error": "Context not found"},  # resolve
          {"id": "test-id", "name": "test-project", "path": str(tmp_path)},  # create
          {"state": "notfound"},  # status
          {"name": "test-project"},  # create env
          {"name": "test-project"},  # start env
        ]

        cmd = WorkCommand()
        args = Namespace()
        cmd.execute(args)

    captured = capsys.readouterr()
    assert "Creating new context" in captured.out
    assert "Development environment 'test-project' is ready!" in captured.out

  def test_work_resumes_stopped_environment(self, tmp_path, capsys):
    """Test work command resumes a stopped environment."""
    with patch.object(WorkCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": str(tmp_path)},  # resolve
        {"state": "stopped"},  # status
        {"name": "test"},  # start
      ]

      # Create config file
      config_path = tmp_path / "dev-env.yaml"
      config_path.write_text("name: test\nimage: ubuntu:22.04")

      cmd = WorkCommand()
      args = Namespace(name="test")
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Starting environment" in captured.out
    assert "Development environment 'test' is ready!" in captured.out


class TestStopCommand:
  """Test stop command functionality."""

  def test_stop_running_environment(self, capsys):
    """Test stopping a running environment."""
    with patch.object(StopCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": "/tmp/test"},  # resolve
        {"state": "running"},  # status
        {"name": "test"},  # stop
      ]

      cmd = StopCommand()
      args = Namespace(name=None)
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Stopping environment 'test'" in captured.out
    assert "Environment 'test' stopped" in captured.out

  def test_stop_already_stopped(self, capsys):
    """Test stopping an already stopped environment."""
    with patch.object(StopCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": "/tmp/test"},  # resolve
        {"state": "stopped"},  # status
      ]

      cmd = StopCommand()
      args = Namespace(name=None)
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Environment 'test' is already stopped" in captured.out


class TestRunCommand:
  """Test run command functionality."""

  def test_run_command_in_environment(self, capsys):
    """Test executing a command in the environment."""
    with patch.object(RunCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": "/tmp/test"},  # resolve
        {"state": "running"},  # status
        {"exit_code": 0, "output": "Hello, World!\n"},  # exec
      ]

      cmd = RunCommand()
      args = Namespace(command=["echo", "Hello, World!"])
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Hello, World!\n" in captured.out

  def test_run_command_environment_not_running(self, capsys):
    """Test run command when environment is not running."""
    with patch.object(RunCommand, "_run_plumbing_command") as mock_run:
      # Context resolution fails - no environment exists
      mock_run.side_effect = [{"error": "Context not found"}]

      cmd = RunCommand()
      args = Namespace(command=["echo", "test"])

      exit_code = cmd.execute(args)

      # Should return non-zero exit code when environment doesn't exist
      assert exit_code != 0

      captured = capsys.readouterr()
      assert "not found" in captured.err


class TestStatusCommand:
  """Test status command functionality."""

  def test_status_current_context(self, capsys):
    """Test showing status of current context."""
    with patch.object(StatusCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {
          "id": "test-id",
          "name": "test",
          "path": "/tmp/test",
          "created_at": "2024-01-01T00:00:00",
          "last_used": "2024-01-01T00:00:00",
        },  # resolve
        {"state": "running", "container_id": "abc123"},  # status
      ]

      cmd = StatusCommand()
      args = Namespace(all=False)
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Context: test" in captured.out
    assert "Path: /tmp/test" in captured.out
    assert "🟢 running" in captured.out

  def test_status_all_contexts(self, capsys):
    """Test showing status of all contexts."""
    with patch.object(StatusCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {
          "contexts": [
            {"id": "id1", "name": "test1", "path": "/tmp/test1"},
            {"id": "id2", "name": "test2", "path": "/tmp/test2"},
          ]
        },  # list
        {"state": "running"},  # status for test1
        {"state": "stopped"},  # status for test2
      ]

      cmd = StatusCommand()
      args = Namespace(all=True)
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Development Environments (2 total)" in captured.out
    assert "🟢 test1" in captured.out
    assert "🟡 test2" in captured.out


class TestShellCommand:
  """Test shell command functionality."""

  @patch("dev_env.commands.plumbing.attach.AttachCommand.execute")
  def test_shell_attaches_to_environment(self, mock_attach, capsys):
    """Test shell command attaches to running environment."""
    with patch.object(ShellCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": "/tmp/test"},  # resolve
        {"state": "running"},  # status
      ]

      cmd = ShellCommand()
      args = Namespace()
      cmd.execute(args)

    captured = capsys.readouterr()
    assert "Entering environment 'test'" in captured.out
    assert mock_attach.called

  def test_shell_environment_not_running(self, capsys):
    """Test shell command when environment is not running."""
    with patch.object(ShellCommand, "_run_plumbing_command") as mock_run:
      mock_run.side_effect = [
        {"id": "test-id", "name": "test", "path": "/tmp/test"},  # resolve
        {"state": "stopped"},  # status
      ]

    cmd = ShellCommand()
    args = Namespace()

    exit_code = cmd.execute(args)

    # Should return non-zero exit code when environment is not running
    assert exit_code != 0

    captured = capsys.readouterr()
    assert "does not exist" in captured.err or "not running" in captured.out
