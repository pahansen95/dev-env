"""Core functionality tests for dev-env"""

import pytest
from unittest.mock import Mock, patch

from dev_env.config import (
  Environment,
  VolumeMount,
  GitConfig,
  NetworkConfig,
  load_environment,
)
from dev_env.state import StateManager
from dev_env.docker import DockerClient
from dev_env.utils import (
  check_docker_available,
  generate_container_name,
  validate_port_mappings,
  validate_bind_mounts,
  format_size,
  ConfigError,
  DockerError,
)


class TestEnvironmentConfig:
  """Test Environment dataclass configuration"""

  def test_minimal_environment(self):
    """Test creating environment with minimal required fields"""
    env = Environment(name="test", base_image="python:3.13")
    assert env.name == "test"
    assert env.base_image == "python:3.13"
    assert env.command is None
    assert env.ports == {}
    assert env.environment == {}
    assert env.volumes == []
    # Test flattened security config
    assert env.user == "1000:1000"
    assert env.drop_capabilities == ["ALL"]
    assert env.no_new_privileges is True

  def test_full_environment(self):
    """Test creating environment with all fields"""
    env = Environment(
      name="test-env",
      base_image="python:3.13",
      command=["sleep", "infinity"],
      environment={"TEST_VAR": "test_value"},
      ports={22: 2222, 8000: 8000},
      volumes=[VolumeMount(source="test-vol", target="/data"), VolumeMount(source="/tmp", target="/tmp")],
      network=NetworkConfig(name="test-network"),
      git=GitConfig(url="https://github.com/test/repo.git"),
      # Test security config
      user="dev:dev",
      memory="4g",
      cpus=4.0,
    )
    assert env.name == "test-env"
    assert env.base_image == "python:3.13"
    assert env.command == ["sleep", "infinity"]
    assert env.user == "dev:dev"
    assert env.memory == "4g"
    assert env.cpus == 4.0

  def test_environment_validation_missing_name(self):
    """Test validation fails when name is missing"""
    with pytest.raises(TypeError):
      Environment(base_image="python:3.13")

  def test_environment_validation_missing_base_image(self):
    """Test validation fails when base_image is missing"""
    with pytest.raises(TypeError):
      Environment(name="test")


class TestVolumeMount:
  """Test VolumeMount dataclass"""

  def test_named_volume(self):
    """Test named volume configuration"""
    vol = VolumeMount(source="data-vol", target="/data", name="data")
    assert vol.name == "data"
    assert vol.source == "data-vol"
    assert vol.target == "/data"
    assert vol.type == "named"
    assert vol.mode == "rw"

  def test_bind_volume(self):
    """Test bind mount configuration"""
    vol = VolumeMount(source="/host/path", target="/container/path", mode="ro")
    assert vol.type == "bind"
    assert vol.mode == "ro"

  def test_volume_type_detection(self):
    """Test automatic volume type detection"""
    # Named volume (relative path)
    vol = VolumeMount(source="vol", target="/data")
    assert vol.type == "named"
    assert vol.name == "vol"  # auto-named from source

    # Bind mount (absolute path)
    vol = VolumeMount(source="/tmp", target="/tmp")
    assert vol.type == "bind"


class TestConfigurationLoading:
  """Test configuration file loading"""

  def test_load_python_config(self, tmp_path):
    """Test loading Python configuration file"""
    config_file = tmp_path / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="python:3.13")
""")

    env = load_environment(config_file)
    assert env.name == "test"
    assert env.base_image == "python:3.13"

  def test_load_nonexistent_file(self, tmp_path):
    """Test loading non-existent configuration file"""
    nonexistent = tmp_path / "nonexistent.py"
    with pytest.raises(FileNotFoundError):
      load_environment(nonexistent)

  def test_load_unsupported_file_type(self, tmp_path):
    """Test loading unsupported file type"""
    unsupported = tmp_path / "config.yaml"
    unsupported.write_text("name: test")

    with pytest.raises(ValueError, match="Only Python configuration files"):
      load_environment(unsupported)


class TestStateManager:
  """Test state management functionality"""

  def test_state_manager_init(self, tmp_path):
    """Test StateManager initialization"""
    state_dir = tmp_path / "state"
    state = StateManager(state_dir)
    assert state.state_dir == state_dir
    assert state.db_path == state_dir / "environments.db"

  def test_save_and_get_environment(self, tmp_path):
    """Test saving and retrieving environment state"""
    state_dir = tmp_path / "state"
    state = StateManager(state_dir)

    env_data = {
      "container_id": "test123",
      "config": {"name": "test", "base_image": "python:3.13"},
    }

    state.save_environment("test-env", env_data)
    retrieved = state.get_environment("test-env")

    assert retrieved is not None
    assert retrieved["container_id"] == "test123"
    assert retrieved["config"]["name"] == "test"

  def test_list_environments(self, tmp_path):
    """Test listing environments"""
    state_dir = tmp_path / "state"
    state = StateManager(state_dir)

    # Initially empty
    envs = state.list_environments()
    assert envs == {}

    # Add environment
    state.save_environment("test1", {"container_id": "123"})
    state.save_environment("test2", {"container_id": "456"})

    envs = state.list_environments()
    assert len(envs) == 2
    assert "test1" in envs
    assert "test2" in envs


class TestDockerClient:
  """Test Docker client functionality"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_docker_client_init(self, mock_conn):
    """Test DockerClient initialization"""
    client = DockerClient()
    assert client.socket_path == "/var/run/docker.sock"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_docker_request(self, mock_conn):
    """Test Docker API request handling"""
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"Id": "test123"}'
    mock_conn.return_value.getresponse.return_value = mock_response

    client = DockerClient()
    result = client._request("GET", "/containers/json")

    assert result == {"Id": "test123"}


class TestUtilities:
  """Test utility functions"""

  @patch("socket.socket")
  def test_check_docker_available_success(self, mock_socket):
    """Test Docker availability check success"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.return_value = None

    result = check_docker_available()
    assert result is True

  @patch("socket.socket")
  def test_check_docker_available_failure(self, mock_socket):
    """Test Docker availability check failure"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.side_effect = ConnectionError()

    result = check_docker_available()
    assert result is False

  def test_generate_container_name(self):
    """Test container name generation"""
    result = generate_container_name("my-env")
    assert result == "dev-env-my-env"

  def test_validate_port_mappings_valid(self):
    """Test validation of valid port mappings"""
    ports = {22: 2222, 80: 8080}
    warnings = validate_port_mappings(ports)
    assert warnings == []

  def test_validate_port_mappings_privileged_ports(self):
    """Test validation warns about privileged ports"""
    ports = {22: 22, 80: 80}
    warnings = validate_port_mappings(ports)
    assert len(warnings) == 2
    assert all("privileged port" in warning.lower() for warning in warnings)

  def test_validate_bind_mounts_existing_paths(self, tmp_path):
    """Test validation of existing bind mount paths"""
    volumes = [
      VolumeMount(source=str(tmp_path), target="/data"),
      VolumeMount(source="data-vol", target="/app"),  # named volume
    ]

    warnings = validate_bind_mounts(volumes)
    assert warnings == []

  def test_format_size(self):
    """Test size formatting utility"""
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"


class TestErrorClasses:
  """Test simplified error handling"""

  def test_config_error_environment_exists(self):
    """Test ConfigError.environment_exists"""
    error = ConfigError.environment_exists("test-env")
    assert "test-env" in error.message
    assert "already exists" in error.message
    assert "down test-env" in error.remediation

  def test_config_error_environment_not_found(self):
    """Test ConfigError.environment_not_found"""
    error = ConfigError.environment_not_found("missing-env")
    assert "missing-env" in error.message
    assert "not found" in error.message
    assert "list" in error.remediation

  def test_docker_error_daemon_unavailable(self):
    """Test DockerError.daemon_unavailable"""
    error = DockerError.daemon_unavailable()
    assert "daemon" in error.message.lower()
    assert "Docker Desktop" in error.remediation

  def test_docker_error_image_pull_failed(self):
    """Test DockerError.image_pull_failed"""
    error = DockerError.image_pull_failed("nonexistent:latest", "404 Not Found")
    assert "nonexistent:latest" in error.message
    assert "404 Not Found" in error.message
    assert "spelling" in error.remediation

  def test_error_format_with_remediation(self):
    """Test error formatting with remediation"""
    error = ConfigError.environment_exists("test")
    formatted = error.format_error()
    assert "Error:" in formatted
    assert "Remediation:" in formatted
    assert error.message in formatted
    assert error.remediation in formatted
