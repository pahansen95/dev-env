"""CLI command tests for dev-env"""

from pathlib import Path
from unittest.mock import Mock, patch
from argparse import Namespace

from dev_env.cli import cmd_up, cmd_down, cmd_list, cmd_exec, cmd_ssh, cmd_logs
from dev_env.config import Environment
from dev_env.utils import ConfigError


class TestCmdUp:
  """Test cmd_up command"""

  @patch("dev_env.cli.check_docker_available", return_value=False)
  def test_cmd_up_docker_unavailable(self, mock_check):
    """Test cmd_up when Docker is unavailable"""
    args = Namespace(config=Path("test.py"), name=None, state_dir=Path("/tmp"))
    result = cmd_up(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  def test_cmd_up_invalid_config(self, mock_load, mock_check):
    """Test cmd_up with invalid configuration"""
    mock_load.side_effect = ConfigError.security_violation("Test error")

    args = Namespace(config=Path("test.py"), name=None, state_dir=Path("/tmp"))
    result = cmd_up(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  def test_cmd_up_environment_exists(self, mock_state_class, mock_load, mock_check):
    """Test cmd_up when environment already exists"""
    env = Environment(name="test", base_image="python:3.13")
    mock_load.return_value = env

    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "existing"}
    mock_state_class.return_value = mock_state

    args = Namespace(config=Path("test.py"), name=None, state_dir=Path("/tmp"))
    result = cmd_up(args)
    assert result != 0


class TestCmdDown:
  """Test cmd_down command"""

  @patch("dev_env.cli.check_docker_available", return_value=False)
  def test_cmd_down_docker_unavailable(self, mock_check):
    """Test cmd_down when Docker is unavailable"""
    args = Namespace(name="test", volumes=False, state_dir=Path("/tmp"))
    result = cmd_down(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  def test_cmd_down_environment_not_found(self, mock_state_class, mock_check):
    """Test cmd_down when environment doesn't exist"""
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    args = Namespace(name="nonexistent", volumes=False, state_dir=Path("/tmp"))
    result = cmd_down(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_down_success(self, mock_docker_class, mock_state_class, mock_check):
    """Test successful cmd_down"""
    # Mock state manager
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": [], "network": None}
    mock_state_class.return_value = mock_state

    # Mock docker client
    mock_docker = Mock()
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", volumes=False, state_dir=Path("/tmp"))
    result = cmd_down(args)
    assert result == 0


class TestCmdList:
  """Test cmd_list command"""

  @patch("dev_env.cli.StateManager")
  def test_cmd_list_empty(self, mock_state_class):
    """Test cmd_list with no environments"""
    mock_state = Mock()
    mock_state.list_environments.return_value = {}
    mock_state_class.return_value = mock_state

    args = Namespace(state_dir=Path("/tmp"))
    result = cmd_list(args)
    assert result == 0

  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  def test_cmd_list_with_environments(self, mock_docker_class, mock_check, mock_state_class):
    """Test cmd_list with existing environments"""
    # Mock state manager
    mock_state = Mock()
    mock_state.list_environments.return_value = {
      "test-env": {
        "container_id": "test123",
        "container_name": "dev-env-test",
        "config": {"base_image": "python:3.13"},
        "volumes": ["vol1"],
        "network": None,
      }
    }
    mock_state_class.return_value = mock_state

    # Mock docker client
    mock_docker = Mock()
    mock_container = {"State": {"Status": "running"}, "Config": {"Image": "python:3.13"}}
    mock_docker.get_container.return_value = mock_container
    mock_docker_class.return_value = mock_docker

    args = Namespace(state_dir=Path("/tmp"))
    result = cmd_list(args)
    assert result == 0


class TestCmdExec:
  """Test cmd_exec command"""

  @patch("dev_env.cli.check_docker_available", return_value=False)
  def test_cmd_exec_docker_unavailable(self, mock_check):
    """Test cmd_exec when Docker is unavailable"""
    args = Namespace(name="test", command=["ls"], state_dir=Path("/tmp"))
    result = cmd_exec(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  def test_cmd_exec_environment_not_found(self, mock_state_class, mock_check):
    """Test cmd_exec when environment doesn't exist"""
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    args = Namespace(name="nonexistent", command=["ls"], state_dir=Path("/tmp"))
    result = cmd_exec(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_exec_success(self, mock_docker_class, mock_state_class, mock_check):
    """Test successful cmd_exec"""
    # Mock state manager
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123"}
    mock_state_class.return_value = mock_state

    # Mock docker client
    mock_docker = Mock()
    mock_docker.get_container.return_value = {"State": {"Status": "running"}}
    mock_docker.exec_run.return_value = (b"output", 0)
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", exec_command=["ls"], state_dir=Path("/tmp"))
    result = cmd_exec(args)
    assert result == 0


class TestCmdSSH:
  """Test cmd_ssh command"""

  @patch("dev_env.cli.StateManager")
  def test_cmd_ssh_environment_not_found(self, mock_state_class):
    """Test cmd_ssh when environment doesn't exist"""
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    args = Namespace(name="nonexistent", state_dir=Path("/tmp"))
    result = cmd_ssh(args)
    assert result != 0

  @patch("dev_env.cli.StateManager")
  def test_cmd_ssh_no_ssh_port(self, mock_state_class):
    """Test cmd_ssh when SSH is not enabled"""
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123", "config": {"ports": {}}}
    mock_state_class.return_value = mock_state

    args = Namespace(name="test", state_dir=Path("/tmp"))
    result = cmd_ssh(args)
    assert result != 0


class TestCmdLogs:
  """Test cmd_logs command"""

  @patch("dev_env.cli.check_docker_available", return_value=False)
  def test_cmd_logs_docker_unavailable(self, mock_check):
    """Test cmd_logs when Docker is unavailable"""
    args = Namespace(name="test", follow=False, tail=None, state_dir=Path("/tmp"))
    result = cmd_logs(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  def test_cmd_logs_environment_not_found(self, mock_state_class, mock_check):
    """Test cmd_logs when environment doesn't exist"""
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    args = Namespace(name="nonexistent", follow=False, tail=None, state_dir=Path("/tmp"))
    result = cmd_logs(args)
    assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_logs_success(self, mock_docker_class, mock_state_class, mock_check):
    """Test successful cmd_logs"""
    # Mock state manager
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123"}
    mock_state_class.return_value = mock_state

    # Mock docker client
    mock_docker = Mock()
    mock_docker.get_container_logs.return_value = b"log output"
    mock_docker_class.return_value = mock_docker

    args = Namespace(name="test", follow=False, tail=None, state_dir=Path("/tmp"))
    result = cmd_logs(args)
    assert result == 0
