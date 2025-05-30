"""Integration tests for dev-env"""

from pathlib import Path
from unittest.mock import Mock, patch
from argparse import Namespace

from dev_env.state import StateManager
from dev_env.cli import cmd_up, cmd_down, cmd_exec


class TestFullWorkflow:
  """Test complete environment lifecycle"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  def test_environment_lifecycle(self, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test full environment creation and teardown workflow"""
    # Setup mocks
    mock_state = Mock()
    mock_state.get_environment.return_value = None  # Initially doesn't exist
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker.get_container.return_value = {"State": {"Status": "running"}}
    mock_docker_class.return_value = mock_docker

    # Create test config
    config_file = tmp_path / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test-env", base_image="python:3.13")
""")

    # Test up command
    up_args = Namespace(config=config_file, name=None, state_dir=tmp_path / "state")
    result = cmd_up(up_args)
    assert result == 0

    # Verify container creation calls
    mock_docker.pull_image.assert_called_once()
    mock_docker.create_container.assert_called_once()
    mock_docker.start_container.assert_called_once_with("test123")
    mock_state.save_environment.assert_called_once()

    # Test down command
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": [], "network": None}

    down_args = Namespace(name="test-env", volumes=False, state_dir=tmp_path / "state")
    result = cmd_down(down_args)
    assert result == 0

    # Verify cleanup calls
    mock_docker.stop_container.assert_called_once_with("test123")
    mock_docker.remove_container.assert_called_once_with("test123")
    mock_state.remove_environment.assert_called_once_with("test-env")

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  def test_environment_with_volumes_and_network(self, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test environment creation with volumes and custom network"""
    # Setup mocks
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker.create_volume.return_value = None
    mock_docker.create_network.return_value = None
    mock_docker_class.return_value = mock_docker

    # Create test config with volumes and network
    config_file = tmp_path / "test.py"
    config_file.write_text(f"""
from dev_env.config import Environment, VolumeMount, NetworkConfig
config = Environment(
    name="test-env",
    base_image="python:3.13",
    volumes=[
        VolumeMount(source="data-vol", target="/data"),
        VolumeMount(source="{tmp_path}", target="/host")
    ],
    network=NetworkConfig(name="test-network")
)
""")

    # Test environment creation
    up_args = Namespace(config=config_file, name=None, state_dir=tmp_path / "state")
    result = cmd_up(up_args)
    assert result == 0

    # Verify volume and network creation
    mock_docker.create_volume.assert_called_once_with("data-vol", labels={"dev-env": "test-env"})
    mock_docker.create_network.assert_called_once()

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.StateManager")
  def test_exec_command_integration(self, mock_state_class, mock_check):
    """Test command execution integration"""
    # Setup state mock
    mock_state = Mock()
    mock_state.get_environment.return_value = {"container_id": "test123"}
    mock_state_class.return_value = mock_state

    # Mock docker client
    with patch("dev_env.cli.DockerClient") as mock_docker_class:
      mock_docker = Mock()
      mock_docker.get_container.return_value = {"State": {"Status": "running"}}
      mock_docker.exec_run.return_value = (b"Hello, World!", 0)
      mock_docker_class.return_value = mock_docker

      # Test exec command
      exec_args = Namespace(name="test-env", command=["echo", "Hello, World!"], state_dir=Path("/tmp"))
      result = cmd_exec(exec_args)
      assert result == 0

      # Verify exec call
      mock_docker.exec_run.assert_called_once_with(container_id="test123", cmd=["echo", "Hello, World!"])


class TestErrorHandling:
  """Test error handling scenarios"""

  def test_environment_already_exists_error(self, tmp_path):
    """Test handling when environment already exists"""
    config_file = tmp_path / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test-env", base_image="python:3.13")
""")

    with patch("dev_env.cli.check_docker_available", return_value=True):
      with patch("dev_env.cli.StateManager") as mock_state_class:
        mock_state = Mock()
        mock_state.get_environment.return_value = {"container_id": "existing"}
        mock_state_class.return_value = mock_state

        up_args = Namespace(config=config_file, name=None, state_dir=tmp_path)
        result = cmd_up(up_args)
        assert result != 0

  @patch("dev_env.cli.check_docker_available", return_value=False)
  def test_docker_unavailable_error(self, mock_check):
    """Test handling when Docker is unavailable"""
    args = Namespace(config=Path("test.py"), name=None, state_dir=Path("/tmp"))
    result = cmd_up(args)
    assert result != 0

  def test_environment_not_found_error(self, tmp_path):
    """Test handling when environment doesn't exist"""
    with patch("dev_env.cli.StateManager") as mock_state_class:
      mock_state = Mock()
      mock_state.get_environment.return_value = None
      mock_state_class.return_value = mock_state

      down_args = Namespace(name="nonexistent", volumes=False, state_dir=tmp_path)
      result = cmd_down(down_args)
      assert result != 0

  def test_invalid_configuration_error(self, tmp_path):
    """Test handling of invalid configuration files"""
    config_file = tmp_path / "invalid.py"
    config_file.write_text("invalid python syntax {")

    with patch("dev_env.cli.check_docker_available", return_value=True):
      up_args = Namespace(config=config_file, name=None, state_dir=tmp_path)
      result = cmd_up(up_args)
      assert result != 0


class TestSecurityValidation:
  """Test security validation integration"""

  def test_security_violation_mount_path(self, tmp_path):
    """Test security validation for dangerous mount paths"""
    config_file = tmp_path / "dangerous.py"
    config_file.write_text("""
from dev_env.config import Environment, VolumeMount
config = Environment(
    name="test-env",
    base_image="python:3.13",
    volumes=[VolumeMount(source="/etc", target="/host-etc")]
)
""")

    with patch("dev_env.cli.check_docker_available", return_value=True):
      up_args = Namespace(config=config_file, name=None, state_dir=tmp_path)
      result = cmd_up(up_args)
      assert result != 0  # Should fail due to security violation

  def test_security_port_binding_validation(self, tmp_path):
    """Test security validation for port bindings"""
    config_file = tmp_path / "insecure_ports.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="test-env",
    base_image="python:3.13",
    ports={22: {"HostPort": 2222, "HostIp": "0.0.0.0"}}
)
""")

    with patch("dev_env.cli.check_docker_available", return_value=True):
      up_args = Namespace(config=config_file, name=None, state_dir=tmp_path)
      result = cmd_up(up_args)
      assert result != 0  # Should fail due to security violation


class TestStateManagement:
  """Test state persistence and management"""

  def test_state_persistence(self, tmp_path):
    """Test that environment state is properly persisted"""
    state_dir = tmp_path / "state"
    state = StateManager(state_dir)

    env_data = {
      "container_id": "test123",
      "container_name": "dev-env-test",
      "config": {"name": "test", "base_image": "python:3.13"},
      "volumes": ["data-vol"],
      "network": "test-network",
    }

    # Save and retrieve state
    state.save_environment("test-env", env_data)
    retrieved = state.get_environment("test-env")

    assert retrieved is not None
    assert retrieved["container_id"] == "test123"
    assert retrieved["config"]["name"] == "test"
    assert retrieved["volumes"] == ["data-vol"]
    assert retrieved["network"] == "test-network"

    # Test listing environments
    environments = state.list_environments()
    assert "test-env" in environments
    assert len(environments) == 1

    # Test removal
    state.remove_environment("test-env")
    assert state.get_environment("test-env") is None
    assert state.list_environments() == {}


class TestNetworkingIntegration:
  """Test networking features integration"""

  @patch("dev_env.cli.check_docker_available", return_value=True)
  @patch("dev_env.cli.DockerClient")
  @patch("dev_env.cli.StateManager")
  def test_custom_network_creation_and_cleanup(self, mock_state_class, mock_docker_class, mock_check, tmp_path):
    """Test custom network creation and cleanup"""
    # Setup mocks for environment creation
    mock_state = Mock()
    mock_state.get_environment.return_value = None
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker.create_network.return_value = None
    mock_docker_class.return_value = mock_docker

    # Create config with custom network
    config_file = tmp_path / "network_test.py"
    config_file.write_text("""
from dev_env.config import Environment, NetworkConfig
config = Environment(
    name="network-test",
    base_image="python:3.13",
    network=NetworkConfig(name="test-net", driver="bridge")
)
""")

    # Test environment creation
    up_args = Namespace(config=config_file, name=None, state_dir=tmp_path / "state")
    result = cmd_up(up_args)
    assert result == 0

    # Verify network creation
    mock_docker.create_network.assert_called_once()

    # Test environment cleanup
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": [], "network": "test-net"}

    down_args = Namespace(name="network-test", volumes=False, state_dir=tmp_path / "state")
    result = cmd_down(down_args)
    assert result == 0

    # Verify network cleanup attempt
    mock_docker.remove_network.assert_called_once_with("test-net")
