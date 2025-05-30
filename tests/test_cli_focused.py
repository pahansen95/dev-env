"""Focused CLI tests for specific coverage improvements"""

from unittest.mock import Mock, patch
from argparse import Namespace

from dev_env.cli import cmd_up, cmd_down


class TestCmdUpNetworkHandling:
  """Test network creation handling in cmd_up"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.validate_port_mappings", return_value=[])
  @patch("dev_env.cli.validate_bind_mounts", return_value=[])
  @patch("dev_env.cli.apply_security_defaults")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_up_network_already_exists_handling(
    self,
    mock_docker_class,
    mock_security,
    mock_validate_mounts,
    mock_validate_ports,
    mock_state_class,
    mock_load_env,
    mock_check_docker,
    tmp_path,
    capsys,
  ):
    """Test cmd_up when network already exists"""
    # Setup mocks
    mock_env = Mock()
    mock_env.name = "test-env"
    mock_env.ports = None
    mock_env.volumes = None
    mock_env.base_image = "python:3.13"
    mock_env.network.name = "existing-network"
    mock_env.environment = {"TEST": "value"}
    mock_load_env.return_value = mock_env
    mock_security.return_value = mock_env

    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.pull_image.return_value = None
    # Network creation fails with "already exists"
    mock_docker.create_network.side_effect = RuntimeError("network already exists")
    mock_docker_class.return_value = mock_docker

    args = Namespace(config=tmp_path / "test.py", name=None, state_dir=tmp_path / "state")

    # Should continue execution despite network already existing
    result = cmd_up(args)

    captured = capsys.readouterr()
    assert "Network already exists: existing-network" in captured.out

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.validate_port_mappings", return_value=[])
  @patch("dev_env.cli.validate_bind_mounts", return_value=[])
  @patch("dev_env.cli.apply_security_defaults")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_up_network_creation_other_error(
    self,
    mock_docker_class,
    mock_security,
    mock_validate_mounts,
    mock_validate_ports,
    mock_state_class,
    mock_load_env,
    mock_check_docker,
    tmp_path,
    capsys,
  ):
    """Test cmd_up when network creation fails with non-exists error"""
    # Setup mocks
    mock_env = Mock()
    mock_env.name = "test-env"
    mock_env.ports = None
    mock_env.volumes = None
    mock_env.base_image = "python:3.13"
    mock_env.network.name = "new-network"
    mock_env.environment = {"TEST": "value"}
    mock_load_env.return_value = mock_env
    mock_security.return_value = mock_env

    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.pull_image.return_value = None
    # Network creation fails with different error
    mock_docker.create_network.side_effect = RuntimeError("Network creation failed")
    mock_docker_class.return_value = mock_docker

    args = Namespace(config=tmp_path / "test.py", name=None, state_dir=tmp_path / "state")

    # Should re-raise the error
    result = cmd_up(args)

    assert result == 1
    captured = capsys.readouterr()
    assert "Network creation failed" in captured.err


class TestCmdUpContainerHandling:
  """Test container creation and execution in cmd_up"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.validate_port_mappings", return_value=[])
  @patch("dev_env.cli.validate_bind_mounts", return_value=[])
  @patch("dev_env.cli.apply_security_defaults")
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.generate_container_name")
  def test_cmd_up_container_start_sequence(
    self,
    mock_gen_name,
    mock_docker_class,
    mock_security,
    mock_validate_mounts,
    mock_validate_ports,
    mock_state_class,
    mock_load_env,
    mock_check_docker,
    tmp_path,
    capsys,
  ):
    """Test successful container creation and start sequence"""
    # Setup mocks
    mock_env = Mock()
    mock_env.name = "test-env"
    mock_env.ports = None
    mock_env.volumes = None
    mock_env.base_image = "python:3.13"
    mock_env.network = None  # No custom network
    mock_env.environment = None
    mock_load_env.return_value = mock_env
    mock_security.return_value = mock_env

    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_gen_name.return_value = "test-container-123"

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "container123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker_class.return_value = mock_docker

    args = Namespace(config=tmp_path / "test.py", name=None, state_dir=tmp_path / "state")

    result = cmd_up(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Creating container: test-container-123" in captured.out
    assert "Starting container..." in captured.out
    assert "Environment 'test-env' is up and running!" in captured.out


class TestCmdDownVolumeHandling:
  """Test volume removal in cmd_down"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_down_skip_volume_removal(self, mock_docker_class, mock_state_class, mock_check_docker, tmp_path, capsys):
    """Test cmd_down skipping volume removal when not specified"""
    # Setup mocks
    mock_state = Mock()
    mock_state.get_environment.return_value = {
      "name": "test-env",
      "container_id": "container123",
      # No volume_name specified
    }
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.remove_container.return_value = None
    mock_docker_class.return_value = mock_docker

    # Mock args without volumes flag
    args = Mock()
    args.name = "test-env"
    args.state_dir = tmp_path / "state"
    args.volumes = False  # Don't remove volumes

    result = cmd_down(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Removing container..." in captured.out
    # Should not try to remove volumes
    mock_docker.remove_volume.assert_not_called()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_down_with_volume_removal(self, mock_docker_class, mock_state_class, mock_check_docker, tmp_path, capsys):
    """Test cmd_down with volume removal"""
    # Setup mocks
    mock_state = Mock()
    mock_state.get_environment.return_value = {
      "name": "test-env",
      "container_id": "container123",
      "volumes": ["test-volume-1", "test-volume-2"],
    }
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.remove_container.return_value = None
    mock_docker.remove_volume.return_value = None
    mock_docker_class.return_value = mock_docker

    # Mock args with volumes flag
    args = Mock()
    args.name = "test-env"
    args.state_dir = tmp_path / "state"
    args.volumes = True  # Remove volumes

    result = cmd_down(args)

    assert result == 0
    captured = capsys.readouterr()
    assert "Removing volume: test-volume-1" in captured.out
    # Should have called remove_volume for both volumes
    assert mock_docker.remove_volume.call_count == 2


class TestCmdErrorMessageFormatting:
  """Test error message formatting in CLI commands"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  def test_cmd_up_config_error_formatting(self, mock_state_class, mock_load_env, mock_check_docker, tmp_path, capsys):
    """Test ConfigError formatting in cmd_up"""
    from dev_env.utils import ConfigError

    # Mock ConfigError with proper format_error method
    error = ConfigError("Test configuration error")
    error.exit_code = 2
    mock_load_env.side_effect = error

    args = Namespace(config=tmp_path / "test.py", name=None, state_dir=tmp_path / "state")

    result = cmd_up(args)

    assert result == 2
    captured = capsys.readouterr()
    assert "Error:" in captured.err  # Should use format_error()


class TestEdgeCaseHandling:
  """Test edge case handling in CLI"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.load_environment")
  @patch("dev_env.cli.StateManager")
  @patch("dev_env.cli.validate_port_mappings", return_value=[])
  @patch("dev_env.cli.validate_bind_mounts", return_value=[])
  @patch("dev_env.cli.apply_security_defaults")
  @patch("dev_env.cli.DockerClient")
  def test_cmd_up_empty_environment_dict(
    self,
    mock_docker_class,
    mock_security,
    mock_validate_mounts,
    mock_validate_ports,
    mock_state_class,
    mock_load_env,
    mock_check_docker,
    tmp_path,
  ):
    """Test cmd_up with empty environment variables"""
    # Setup mocks
    mock_env = Mock()
    mock_env.name = "test-env"
    mock_env.ports = None
    mock_env.volumes = None
    mock_env.base_image = "python:3.13"
    mock_env.network = None
    mock_env.environment = {}  # Empty environment dict
    mock_load_env.return_value = mock_env
    mock_security.return_value = mock_env

    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.ping.return_value = True
    mock_docker.pull_image.side_effect = Exception("Test early termination")
    mock_docker_class.return_value = mock_docker

    args = Namespace(config=tmp_path / "test.py", name=None, state_dir=tmp_path / "state")

    with patch("dev_env.cli.generate_container_name") as mock_gen_name:
      mock_gen_name.return_value = "test-container"

      result = cmd_up(args)

      # Should handle empty environment dict correctly
      assert result == 0  # Empty environment dict is valid
