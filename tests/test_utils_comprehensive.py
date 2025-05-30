# tests/test_utils_comprehensive.py

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
from dev_env.utils import (
  setup_ssh_server,
  inject_ssh_key,
  get_host_ssh_key,
  setup_git_in_container,
  clone_git_repository,
  validate_volume_security,
  validate_port_security,
  wait_for_port,
  ConfigError,
)


class TestSSHOperations:
  """Test SSH-related utilities"""

  def test_setup_ssh_server_debian(self):
    """Test SSH server setup on Debian-based systems"""
    mock_docker = Mock()
    container_id = "test123"

    # Mock apt-get detection
    mock_docker.exec_run.side_effect = [
      (b"/usr/bin/apt-get", 0),  # which apt-get
      (b"", 0),  # apt-get update
      (b"", 0),  # apt-get install
      (b"", 0),  # mkdir
      (b"", 0),  # chmod
      (b"", 0),  # ssh-keygen -A
      (b"", 0),  # write sshd_config
    ]

    setup_ssh_server(mock_docker, container_id)

    # Verify package installation
    calls = [str(call) for call in mock_docker.exec_run.call_args_list]
    assert any("apt-get" in call and "openssh-server" in call for call in calls)
    assert any("ssh-keygen" in call and "-A" in call for call in calls)

  def test_setup_ssh_server_alpine(self):
    """Test SSH server setup on Alpine Linux"""
    mock_docker = Mock()
    container_id = "test123"

    # Mock Alpine detection
    mock_docker.exec_run.side_effect = [
      (b"", 1),  # which apt-get - fails
      (b"", 1),  # which yum - fails
      (b"/sbin/apk", 0),  # which apk - succeeds
      (b"", 0),  # apk add openssh
      (b"", 0),  # mkdir
      (b"", 0),  # chmod
      (b"", 0),  # ssh-keygen -A
      (b"", 0),  # write sshd_config
    ]

    setup_ssh_server(mock_docker, container_id)

    calls = [str(call) for call in mock_docker.exec_run.call_args_list]
    assert any("apk" in call and "openssh" in call for call in calls)

  def test_inject_ssh_key(self):
    """Test SSH key injection"""
    mock_docker = Mock()
    container_id = "test123"
    public_key = "ssh-rsa AAAAB3... user@host"

    inject_ssh_key(mock_docker, container_id, public_key)

    # Verify key was written and permissions set
    calls = mock_docker.exec_run.call_args_list
    assert len(calls) == 2
    assert "authorized_keys" in str(calls[0])
    assert public_key in str(calls[0])
    assert "chmod" in str(calls[1]) and "600" in str(calls[1])

  @patch("pathlib.Path.exists")
  @patch("pathlib.Path.read_text")
  def test_get_host_ssh_key_existing(self, mock_read, mock_exists):
    """Test retrieving existing SSH key"""
    mock_exists.return_value = True
    mock_read.return_value = "ssh-rsa AAAAB3... user@host\n"

    key = get_host_ssh_key()
    assert key == "ssh-rsa AAAAB3... user@host"

  @patch("pathlib.Path.exists")
  @patch("dev_env.utils.generate_ssh_key_pair")
  def test_get_host_ssh_key_generate(self, mock_generate, mock_exists):
    """Test SSH key generation when none exists"""
    mock_exists.return_value = False
    mock_generate.return_value = ("private_key", "public_key")

    with patch("pathlib.Path.write_text"), patch("pathlib.Path.chmod"):
      key = get_host_ssh_key()
      assert key == "public_key"
      mock_generate.assert_called_once()


class TestGitOperations:
  """Test Git-related utilities"""

  def test_setup_git_in_container(self):
    """Test Git setup and repository cloning in container"""
    mock_docker = Mock()
    container_id = "test123"
    mock_git_config = Mock()
    mock_git_config.url = "https://github.com/test/repo.git"
    mock_git_config.path = "/workspace"
    mock_git_config.shallow = True
    mock_git_config.branch = "main"

    host_config = {"user.name": "Test User", "user.email": "test@example.com"}

    # Mock git already installed
    mock_docker.exec_run.side_effect = [
      (b"/usr/bin/git", 0),  # which git
      (b"", 0),  # git config user.name
      (b"", 0),  # git config user.email
      (b"", 0),  # mkdir
      (b"", 0),  # git clone
    ]

    setup_git_in_container(mock_docker, container_id, mock_git_config, host_config)

    # Verify git config was set
    calls = [str(call) for call in mock_docker.exec_run.call_args_list]
    assert any("user.name" in call and "Test User" in call for call in calls)
    assert any("user.email" in call and "test@example.com" in call for call in calls)
    assert any("--depth" in call and "1" in call for call in calls)

  @patch("shutil.which")
  @patch("dev_env.utils.run_command")
  def test_clone_git_repository(self, mock_run, mock_which):
    """Test local Git repository cloning"""
    mock_which.return_value = "/usr/bin/git"
    mock_run.return_value = (0, "", "")

    with tempfile.TemporaryDirectory() as tmpdir:
      target = Path(tmpdir) / "repo"
      clone_git_repository("https://github.com/test/repo.git", target, branch="develop", shallow=True)

      mock_run.assert_called_once()
      cmd = mock_run.call_args[0][0]
      assert cmd[0] == "git"
      assert cmd[1] == "clone"
      assert "--depth" in cmd
      assert "--branch" in cmd
      assert "develop" in cmd


class TestSecurityValidation:
  """Test security validation functions"""

  def test_validate_volume_security_forbidden_paths(self):
    """Test detection of forbidden mount paths"""
    from dev_env.config import VolumeMount

    # Test forbidden system paths
    dangerous_volumes = [
      VolumeMount(source="/etc", target="/host-etc"),
      VolumeMount(source="/var/run/docker.sock", target="/docker.sock"),
      VolumeMount(source="/", target="/host-root"),
    ]

    for vol in dangerous_volumes:
      with pytest.raises(ConfigError) as exc_info:
        validate_volume_security([vol])
      assert "security violation" in str(exc_info.value)

  def test_validate_volume_security_safe_paths(self):
    """Test safe volume paths pass validation"""
    from dev_env.config import VolumeMount

    safe_volumes = [
      VolumeMount(source="data-volume", target="/data"),
      VolumeMount(source="my-volume", target="/app"),
      VolumeMount(source="/Users/user/project", target="/workspace"),
    ]

    # Should not raise
    validate_volume_security(safe_volumes)

  def test_validate_port_security_all_interfaces(self):
    """Test rejection of 0.0.0.0 binding"""
    ports = {22: {"HostPort": 2222, "HostIp": "0.0.0.0"}}

    with pytest.raises(ConfigError) as exc_info:
      validate_port_security(ports)
    assert "0.0.0.0" in str(exc_info.value)

  def test_validate_port_security_localhost_default(self):
    """Test localhost is set as default"""
    ports = {
      22: {"HostPort": 2222}  # No HostIp specified
    }

    validate_port_security(ports)
    assert ports[22]["HostIp"] == "127.0.0.1"


class TestNetworkOperations:
  """Test network utilities"""

  @patch("socket.socket")
  def test_wait_for_port_success(self, mock_socket_class):
    """Test successful port wait"""
    mock_sock = Mock()
    mock_socket_class.return_value = mock_sock
    mock_sock.connect_ex.return_value = 0  # Success

    result = wait_for_port("localhost", 8080, timeout=1)
    assert result is True

  @patch("socket.socket")
  @patch("time.time")
  def test_wait_for_port_timeout(self, mock_time, mock_socket_class):
    """Test port wait timeout"""
    mock_sock = Mock()
    mock_socket_class.return_value = mock_sock
    mock_sock.connect_ex.return_value = 1  # Connection refused

    # Simulate timeout
    mock_time.side_effect = [0, 0.5, 1, 1.5, 2]

    result = wait_for_port("localhost", 8080, timeout=1)
    assert result is False


class TestErrorClasses:
  """Test error formatting and remediation"""

  def test_error_remediation_formatting(self):
    """Test error messages include helpful remediation"""
    error = ConfigError.environment_exists("test-env")
    formatted = error.format_error()

    assert "Error:" in formatted
    assert "Remediation:" in formatted
    assert "test-env" in formatted
    assert "down test-env" in formatted

  def test_custom_exit_codes(self):
    """Test errors have appropriate exit codes"""
    assert ConfigError.environment_exists("test").exit_code == 1
    assert ConfigError.security_violation("test").exit_code == 2
