# tests/test_cli_error_paths.py

from pathlib import Path
from unittest.mock import Mock, patch
from argparse import Namespace
from dev_env.cli import cmd_up, cmd_down, cmd_exec


class TestCLIErrorPaths:
  """Test error handling paths in CLI commands"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  def test_cmd_up_image_pull_failure(self, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test handling of image pull failures"""
    # Setup mocks
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    # First pull attempt fails
    mock_docker.pull_image.side_effect = Exception("Network error")
    # Local image check also fails
    mock_docker._request.side_effect = RuntimeError("Image not found")
    mock_docker_class.return_value = mock_docker

    # Create config
    config_file = tmp_path / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="nonexistent:latest")
""")

    args = Namespace(config=config_file, name=None, state_dir=tmp_path)
    result = cmd_up(args)

    assert result != 0  # Should fail with appropriate exit code
    # No cleanup needed since state was never saved
    mock_state.remove_environment.assert_not_called()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  @patch("builtins.input", return_value="n")  # User declines to continue
  def test_cmd_up_user_abort_on_warnings(self, mock_input, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test user aborting on configuration warnings"""
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    # Create config with privileged port
    config_file = tmp_path / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="test",
    base_image="python:3.13",
    ports={80: {"HostPort": 80}}  # Privileged port warning
)
""")

    args = Namespace(config=config_file, name=None, state_dir=tmp_path)
    result = cmd_up(args)

    assert result == 1  # User aborted
    mock_input.assert_called_once()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  def test_cmd_up_ssh_setup_failure(self, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test graceful handling of SSH setup failures"""
    # Setup successful container creation
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.create_container.return_value = "test123"
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker_class.return_value = mock_docker

    # Make SSH setup fail
    with patch("dev_env.utils.setup_ssh_server", side_effect=Exception("SSH install failed")):
      config_file = tmp_path / "test.py"
      config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="test",
    base_image="python:3.13",
    ports={22: {"HostPort": 2222}}
)
""")

      args = Namespace(config=config_file, name=None, state_dir=tmp_path)
      result = cmd_up(args)

      # Should succeed but with SSH warning
      assert result == 0
      mock_state.save_environment.assert_called_once()


class TestCmdExecErrorPaths:
  """Test exec command error scenarios"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_exec_container_not_running(self, mock_docker_class, mock_state_class, mock_check):
    """Test exec on stopped container"""
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123"}
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.get_container.return_value = {"State": {"Status": "exited"}}
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", command=["ls"], state_dir=Path("/tmp"))
    result = cmd_exec(args)

    assert result != 0
    mock_docker.exec_run.assert_not_called()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_exec_command_failure(self, mock_docker_class, mock_state_class, mock_check):
    """Test handling of failed command execution"""
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123"}
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.get_container.return_value = {"State": {"Status": "running"}}
    mock_docker.exec_run.return_value = (b"Command not found", 127)
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", exec_command=["nonexistent"], state_dir=Path("/tmp"))
    result = cmd_exec(args)

    assert result == 127  # Exit code propagated


class TestCmdDownErrorPaths:
  """Test down command error scenarios"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_down_container_already_removed(self, mock_docker_class, mock_state_class, mock_check):
    """Test handling when container is already gone"""
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": ["vol1"], "network": None}
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    # Container doesn't exist
    mock_docker.stop_container.side_effect = RuntimeError("No such container")
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", volumes=False, state_dir=Path("/tmp"))
    result = cmd_down(args)

    # Should handle gracefully
    assert result == 1
    mock_state.remove_environment.assert_not_called()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_down_volume_removal_failure(self, mock_docker_class, mock_state_class, mock_check):
    """Test handling of volume removal failures"""
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": ["vol1", "vol2"], "network": None}
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    # Volume removal fails (maybe in use)
    mock_docker.remove_volume.side_effect = Exception("Volume in use")
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", volumes=True, state_dir=Path("/tmp"))
    result = cmd_down(args)

    # Should complete but with warnings
    assert result == 0
    mock_state.remove_environment.assert_called_once()
    assert mock_docker.remove_volume.call_count == 2
