"""Tests for utility functions"""

import tempfile
from unittest.mock import Mock, patch

from dev_env.utils import (
  check_docker_available,
  generate_container_name,
  validate_port_mappings,
  validate_bind_mounts,
  format_size,
  DevEnvError,
  DockerNotAvailableError,
  EnvironmentExistsError,
  EnvironmentNotFoundError,
  ContainerNotRunningError,
  ImagePullError,
  SSHNotEnabledError,
)


class TestDockerAvailability:
  """Test Docker availability checking"""

  @patch("socket.socket")
  def test_check_docker_available_success(self, mock_socket):
    """Test Docker is available when socket connection succeeds"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.return_value = None  # Success

    result = check_docker_available()

    assert result is True
    mock_sock.connect.assert_called_once_with("/var/run/docker.sock")
    mock_sock.close.assert_called_once()

  @patch("socket.socket")
  def test_check_docker_available_connection_error(self, mock_socket):
    """Test Docker is not available when socket connection fails"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.side_effect = ConnectionError("No such file or directory")

    result = check_docker_available()

    assert result is False
    mock_sock.close.assert_called_once()

  @patch("socket.socket")
  def test_check_docker_available_permission_error(self, mock_socket):
    """Test Docker is not available when permission denied"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.side_effect = PermissionError("Permission denied")

    result = check_docker_available()

    assert result is False
    mock_sock.close.assert_called_once()

  @patch("socket.socket")
  def test_check_docker_available_file_not_found(self, mock_socket):
    """Test Docker is not available when socket file doesn't exist"""
    mock_sock = Mock()
    mock_socket.return_value = mock_sock
    mock_sock.connect.side_effect = FileNotFoundError("No such file")

    result = check_docker_available()

    assert result is False
    mock_sock.close.assert_called_once()


class TestContainerNaming:
  """Test container name generation"""

  def test_generate_container_name_simple(self):
    """Test generating container name for simple environment name"""
    result = generate_container_name("my-env")
    assert result == "dev-env-my-env"

  def test_generate_container_name_with_special_chars(self):
    """Test container name generation handles special characters"""
    result = generate_container_name("my_env-123")
    assert result == "dev-env-my_env-123"

  def test_generate_container_name_empty(self):
    """Test container name generation with empty name"""
    result = generate_container_name("")
    assert result == "dev-env-"

  def test_generate_container_name_long(self):
    """Test container name generation with long name"""
    long_name = "very-long-environment-name-that-might-cause-issues"
    result = generate_container_name(long_name)
    assert result == f"dev-env-{long_name}"
    assert result.startswith("dev-env-")


class TestPortValidation:
  """Test port mapping validation"""

  def test_validate_port_mappings_valid(self):
    """Test validation of valid port mappings"""
    ports = {22: 2222, 80: 8080, 443: 4443}
    warnings = validate_port_mappings(ports)
    assert warnings == []

  def test_validate_port_mappings_privileged_ports(self):
    """Test validation warns about privileged ports"""
    ports = {22: 22, 80: 80, 443: 443}
    warnings = validate_port_mappings(ports)

    assert len(warnings) == 3
    assert all("privileged port" in warning.lower() for warning in warnings)
    assert "22" in warnings[0]
    assert "80" in warnings[1]
    assert "443" in warnings[2]

  def test_validate_port_mappings_high_ports(self):
    """Test validation of high port numbers"""
    ports = {8080: 65535, 9000: 65536}  # 65536 is invalid
    warnings = validate_port_mappings(ports)

    assert len(warnings) == 1
    assert "65536" in warnings[0]
    assert "port range" in warnings[0].lower()

  def test_validate_port_mappings_zero_ports(self):
    """Test validation of zero and negative ports"""
    ports = {0: 8080, 80: 0, -1: 8081}
    warnings = validate_port_mappings(ports)

    assert len(warnings) >= 2  # At least warn about 0 and -1
    warning_text = " ".join(warnings)
    assert "0" in warning_text

  def test_validate_port_mappings_complex_format(self):
    """Test validation of complex port mapping format"""
    ports = {22: {"HostPort": "22", "HostIp": "127.0.0.1"}, 80: {"HostPort": "8080"}, 443: 4443}
    warnings = validate_port_mappings(ports)

    # Should warn about privileged port 22
    assert len(warnings) == 1
    assert "22" in warnings[0]

  def test_validate_port_mappings_empty(self):
    """Test validation of empty port mappings"""
    warnings = validate_port_mappings({})
    assert warnings == []

  def test_validate_port_mappings_none(self):
    """Test validation of None port mappings"""
    warnings = validate_port_mappings(None)
    assert warnings == []


class TestBindMountValidation:
  """Test bind mount validation"""

  def test_validate_bind_mounts_existing_paths(self):
    """Test validation of existing bind mount paths"""
    with tempfile.TemporaryDirectory() as temp_dir:
      volumes = [
        type("Volume", (), {"type": "bind", "source": temp_dir, "target": "/data"})(),
        type("Volume", (), {"type": "named", "source": "data-vol", "target": "/app"})(),
      ]

      warnings = validate_bind_mounts(volumes)
      assert warnings == []

  def test_validate_bind_mounts_nonexistent_paths(self):
    """Test validation warns about non-existent bind mount paths"""
    volumes = [
      type("Volume", (), {"type": "bind", "source": "/nonexistent/path", "target": "/data"})(),
      type("Volume", (), {"type": "bind", "source": "/another/missing", "target": "/app"})(),
    ]

    warnings = validate_bind_mounts(volumes)
    assert len(warnings) == 2
    assert "/nonexistent/path" in warnings[0]
    assert "/another/missing" in warnings[1]
    assert all("does not exist" in warning for warning in warnings)

  def test_validate_bind_mounts_mixed_types(self):
    """Test validation handles mix of bind mounts and named volumes"""
    with tempfile.TemporaryDirectory() as temp_dir:
      volumes = [
        type("Volume", (), {"type": "bind", "source": temp_dir, "target": "/existing"})(),
        type("Volume", (), {"type": "bind", "source": "/missing", "target": "/missing"})(),
        type("Volume", (), {"type": "named", "source": "data-vol", "target": "/data"})(),
      ]

      warnings = validate_bind_mounts(volumes)
      assert len(warnings) == 1
      assert "/missing" in warnings[0]

  def test_validate_bind_mounts_empty(self):
    """Test validation of empty volume list"""
    warnings = validate_bind_mounts([])
    assert warnings == []

  def test_validate_bind_mounts_none(self):
    """Test validation of None volume list"""
    warnings = validate_bind_mounts(None)
    assert warnings == []


class TestSizeFormatting:
  """Test size formatting utility"""

  def test_format_size_bytes(self):
    """Test formatting byte sizes"""
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(1023) == "1023 B"

  def test_format_size_kilobytes(self):
    """Test formatting kilobyte sizes"""
    assert format_size(1024) == "1.0 KB"
    assert format_size(1536) == "1.5 KB"
    assert format_size(2048) == "2.0 KB"

  def test_format_size_megabytes(self):
    """Test formatting megabyte sizes"""
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(int(1.5 * 1024 * 1024)) == "1.5 MB"
    assert format_size(10 * 1024 * 1024) == "10.0 MB"

  def test_format_size_gigabytes(self):
    """Test formatting gigabyte sizes"""
    assert format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert format_size(int(2.5 * 1024 * 1024 * 1024)) == "2.5 GB"

  def test_format_size_terabytes(self):
    """Test formatting terabyte sizes"""
    tb_size = 1024 * 1024 * 1024 * 1024
    assert format_size(tb_size) == "1.0 TB"
    assert format_size(int(1.5 * tb_size)) == "1.5 TB"

  def test_format_size_negative(self):
    """Test formatting negative sizes"""
    # Should handle gracefully
    result = format_size(-1024)
    assert "KB" in result or "B" in result

  def test_format_size_very_large(self):
    """Test formatting very large sizes"""
    huge_size = 1024**6  # Exabytes
    result = format_size(huge_size)
    assert isinstance(result, str)
    assert any(unit in result for unit in ["TB", "PB", "EB"])


class TestErrorClasses:
  """Test custom error classes"""

  def test_dev_env_error_basic(self):
    """Test basic DevEnvError"""
    error = DevEnvError("Something went wrong")
    assert str(error) == "Something went wrong"
    assert error.message == "Something went wrong"
    assert error.remediation is None
    assert error.exit_code == 1

  def test_dev_env_error_with_remediation(self):
    """Test DevEnvError with remediation"""
    error = DevEnvError(
      "Docker not found", remediation="Install Docker: https://docs.docker.com/get-docker/", exit_code=127
    )

    formatted = error.format_error()
    assert "Docker not found" in formatted
    assert "Install Docker" in formatted
    assert error.exit_code == 127

  def test_docker_not_available_error(self):
    """Test DockerNotAvailableError"""
    error = DockerNotAvailableError()
    formatted = error.format_error()

    assert "Docker daemon is not running" in formatted
    assert "docker --version" in formatted
    assert "systemctl start docker" in formatted

  def test_environment_exists_error(self):
    """Test EnvironmentExistsError"""
    error = EnvironmentExistsError("my-env")
    formatted = error.format_error()

    assert "Environment 'my-env' already exists" in formatted
    assert "dev-env down my-env" in formatted

  def test_environment_not_found_error(self):
    """Test EnvironmentNotFoundError"""
    error = EnvironmentNotFoundError("missing-env")
    formatted = error.format_error()

    assert "Environment 'missing-env' not found" in formatted
    assert "dev-env list" in formatted

  def test_container_not_running_error(self):
    """Test ContainerNotRunningError"""
    error = ContainerNotRunningError("stopped-env")
    formatted = error.format_error()

    assert "Environment 'stopped-env' is not running" in formatted
    assert "dev-env up" in formatted

  def test_image_pull_error(self):
    """Test ImagePullError"""
    error = ImagePullError("nonexistent:latest", "404 Not Found")
    formatted = error.format_error()

    assert "Failed to pull image 'nonexistent:latest'" in formatted
    assert "404 Not Found" in formatted
    assert "docker pull" in formatted

  def test_ssh_not_enabled_error(self):
    """Test SSHNotEnabledError"""
    error = SSHNotEnabledError("no-ssh-env")
    formatted = error.format_error()

    assert "SSH is not enabled for environment 'no-ssh-env'" in formatted
    assert "ports" in formatted.lower()
    assert "22" in formatted


class TestSSHUtilities:
  """Test SSH-related utility functions"""

  @patch("dev_env.utils.subprocess.run")
  @patch("dev_env.utils.Path.exists")
  def test_get_host_ssh_key_exists(self, mock_exists, mock_run):
    """Test getting existing host SSH key"""
    mock_exists.return_value = True
    mock_run.return_value.stdout = "ssh-rsa AAAA... user@host"
    mock_run.return_value.returncode = 0

    from dev_env.utils import get_host_ssh_key

    result = get_host_ssh_key()

    assert result == "ssh-rsa AAAA... user@host"
    mock_run.assert_called_once()

  @patch("dev_env.utils.subprocess.run")
  @patch("dev_env.utils.Path.exists")
  def test_get_host_ssh_key_not_exists(self, mock_exists, mock_run):
    """Test handling when host SSH key doesn't exist"""
    mock_exists.return_value = False
    mock_run.return_value.returncode = 0

    from dev_env.utils import get_host_ssh_key

    result = get_host_ssh_key()

    # Should generate new key
    assert isinstance(result, str)
    assert mock_run.call_count >= 1  # At least one call to ssh-keygen


class TestGitUtilities:
  """Test Git-related utility functions"""

  @patch("dev_env.utils.subprocess.run")
  def test_get_host_git_config(self, mock_run):
    """Test getting host Git configuration"""
    mock_run.side_effect = [
      type("Result", (), {"stdout": "John Doe", "returncode": 0})(),
      type("Result", (), {"stdout": "john@example.com", "returncode": 0})(),
    ]

    from dev_env.utils import get_host_git_config

    result = get_host_git_config()

    assert result == {"user.name": "John Doe", "user.email": "john@example.com"}

  @patch("dev_env.utils.subprocess.run")
  def test_get_host_git_config_missing(self, mock_run):
    """Test handling missing Git configuration"""
    mock_run.side_effect = [
      type("Result", (), {"stdout": "", "returncode": 1})(),
      type("Result", (), {"stdout": "", "returncode": 1})(),
    ]

    from dev_env.utils import get_host_git_config

    result = get_host_git_config()

    # Should return empty dict when no config found
    assert result == {}

  @patch("dev_env.utils.get_host_git_config")
  def test_setup_git_in_container_basic(self, mock_get_config):
    """Test basic Git setup in container"""
    mock_get_config.return_value = {"user.name": "Test User", "user.email": "test@example.com"}
    mock_docker = Mock()
    mock_docker.exec_run.return_value = (b"Success", 0)

    from dev_env.utils import setup_git_in_container
    from dev_env.config import GitConfig

    git_config = GitConfig(url="https://github.com/test/repo.git", branch="main", path="/workspace")

    host_config = {"user.name": "Test User", "user.email": "test@example.com"}

    setup_git_in_container(mock_docker, "container123", git_config, host_config)

    # Verify some Git commands were run
    assert mock_docker.exec_run.call_count > 0
