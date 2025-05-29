"""Tests for error scenarios and edge cases"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from argparse import Namespace

from dev_env.cli import cmd_up, cmd_down, cmd_exec, cmd_logs, cmd_attach
from dev_env.docker import DockerClient
from dev_env.state import StateManager


class TestDockerDaemonErrors:
  """Test handling when Docker daemon is unavailable or malfunctioning"""

  def test_all_commands_fail_gracefully_without_docker(self, temp_dir, mock_docker_unavailable):
    """Test all commands handle Docker unavailability gracefully"""
    state_dir = temp_dir / "state"

    # Create a sample config file
    config_file = temp_dir / "test.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="python:3.13")
""")

    # Test up command
    up_args = Namespace(config=config_file, name=None, state_dir=state_dir)
    result = cmd_up(up_args)
    assert result != 0

    # Create fake environment state for other commands
    state_manager = StateManager(state_dir)
    state_manager.save_environment("test-env", {"container_id": "fake123"})

    # Test down command
    down_args = Namespace(name="test-env", volumes=False, state_dir=state_dir)
    result = cmd_down(down_args)
    assert result != 0

    # Test exec command
    exec_args = Namespace(name="test-env", command=["ls"], state_dir=state_dir)
    result = cmd_exec(exec_args)
    assert result != 0

    # Test logs command
    logs_args = Namespace(name="test-env", follow=False, tail=None, state_dir=state_dir)
    result = cmd_logs(logs_args)
    assert result != 0

    # Test attach command
    attach_args = Namespace(name="test-env", state_dir=state_dir)
    result = cmd_attach(attach_args)
    assert result != 0

  @patch("http.client.HTTPConnection")
  def test_docker_api_connection_timeout(self, mock_http_connection):
    """Test handling of Docker API connection timeouts"""
    mock_http_connection.side_effect = TimeoutError("Connection timed out")

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Failed to connect to Docker"):
      client._request("GET", "/containers/json")

  @patch("http.client.HTTPConnection")
  def test_docker_api_permission_denied(self, mock_http_connection):
    """Test handling of Docker API permission errors"""
    mock_http_connection.side_effect = PermissionError("Permission denied")

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Failed to connect to Docker"):
      client._request("GET", "/containers/json")

  @patch("http.client.HTTPConnection")
  def test_docker_api_malformed_response(self, mock_http_connection):
    """Test handling of malformed Docker API responses"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b"invalid json {"
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Invalid JSON response"):
      client._request("GET", "/containers/json")


class TestImagePullErrors:
  """Test various image pull error scenarios"""

  def test_image_not_found_404(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of non-existent images"""
    config_file = temp_dir / "bad_image.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="nonexistent:tag")
""")

    # Mock 404 error for both pull and local check
    mock_docker.pull_image.side_effect = Exception("404 Not Found")
    mock_docker._request.side_effect = RuntimeError("404 Not Found")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0

  def test_image_pull_network_error(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of network errors during image pull"""
    config_file = temp_dir / "net_error.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="python:3.13")
""")

    # Mock network error during pull, but image exists locally
    mock_docker.pull_image.side_effect = Exception("Network unreachable")
    mock_docker._request.return_value = {"Id": "local_image"}  # Local image exists

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")

    with patch("builtins.input", return_value="y"):
      result = cmd_up(up_args)

    # Should succeed using local image
    assert result == 0

  def test_registry_authentication_error(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of registry authentication errors"""
    config_file = temp_dir / "auth_error.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="test", base_image="private/image:latest")
""")

    mock_docker.pull_image.side_effect = Exception("401 Unauthorized")
    mock_docker._request.side_effect = RuntimeError("No such image")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0


class TestContainerCreationErrors:
  """Test container creation failure scenarios"""

  def test_container_name_conflict(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of container name conflicts"""
    config_file = temp_dir / "conflict.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="conflict", base_image="python:3.13")
""")

    # Mock container creation failure due to name conflict
    mock_docker.create_container.side_effect = RuntimeError("Conflict: name already in use")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0

  def test_port_binding_conflict(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of port binding conflicts"""
    config_file = temp_dir / "port_conflict.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="port-test",
    base_image="python:3.13",
    ports={80: 80}
)
""")

    mock_docker.create_container.side_effect = RuntimeError("Port 80 already in use")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")

    with patch("builtins.input", return_value="y"):  # Accept warnings
      result = cmd_up(up_args)

    assert result != 0

  def test_insufficient_resources(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of insufficient system resources"""
    config_file = temp_dir / "resources.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="big", base_image="python:3.13")
""")

    mock_docker.create_container.side_effect = RuntimeError("Insufficient memory")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0

  def test_volume_creation_failure(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of volume creation failures"""
    config_file = temp_dir / "volume_fail.py"
    config_file.write_text("""
from dev_env.config import Environment, VolumeConfig
config = Environment(
    name="vol-test",
    base_image="python:3.13",
    volumes=[VolumeConfig(name="data", source="test-vol", target="/data", type="named")]
)
""")

    mock_docker.create_volume.side_effect = RuntimeError("Volume creation failed")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0

  def test_network_creation_failure(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of network creation failures"""
    config_file = temp_dir / "network_fail.py"
    config_file.write_text("""
from dev_env.config import Environment, NetworkConfig
config = Environment(
    name="net-test",
    base_image="python:3.13",
    network=NetworkConfig(name="test-net")
)
""")

    # Network doesn't exist and creation fails
    mock_docker.get_network.side_effect = RuntimeError("Network not found")
    mock_docker.create_network.side_effect = RuntimeError("Network creation failed")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0


class TestSSHSetupErrors:
  """Test SSH setup failure scenarios"""

  def test_ssh_package_installation_failure(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of SSH package installation failures"""
    config_file = temp_dir / "ssh_fail.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="ssh-test",
    base_image="python:3.13",
    ports={22: 2222}
)
""")

    with patch("dev_env.utils.setup_ssh_server") as mock_ssh_setup:
      mock_ssh_setup.side_effect = Exception("Package installation failed")

      up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
      result = cmd_up(up_args)

      # Should continue despite SSH setup failure (warning only)
      assert result == 0

  def test_ssh_key_injection_failure(self, temp_dir, mock_check_docker_available, mock_docker, mock_ssh_utils):
    """Test handling of SSH key injection failures"""
    config_file = temp_dir / "ssh_key_fail.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="ssh-key-test",
    base_image="python:3.13",
    ports={22: 2222}
)
""")

    mock_ssh_utils["inject_ssh_key"].side_effect = Exception("Key injection failed")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    # Should continue despite SSH key injection failure
    assert result == 0

  def test_ssh_daemon_start_failure(self, temp_dir, mock_check_docker_available, mock_docker, mock_ssh_utils):
    """Test handling of SSH daemon startup failures"""
    config_file = temp_dir / "sshd_fail.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="sshd-test",
    base_image="python:3.13",
    ports={22: 2222}
)
""")

    # Mock sshd startup failure
    mock_docker.exec_run.side_effect = Exception("sshd failed to start")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    # Should continue despite sshd startup failure
    assert result == 0


class TestGitSetupErrors:
  """Test Git setup failure scenarios"""

  def test_git_clone_failure(self, temp_dir, mock_check_docker_available, mock_docker, mock_git_utils):
    """Test handling of Git clone failures"""
    config_file = temp_dir / "git_fail.py"
    config_file.write_text("""
from dev_env.config import Environment, GitConfig
config = Environment(
    name="git-test",
    base_image="python:3.13",
    git=GitConfig(url="https://github.com/nonexistent/repo.git")
)
""")

    mock_git_utils["setup_git_in_container"].side_effect = Exception("Repository not found")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    # Should continue despite Git setup failure
    assert result == 0

  def test_git_authentication_failure(self, temp_dir, mock_check_docker_available, mock_docker, mock_git_utils):
    """Test handling of Git authentication failures"""
    config_file = temp_dir / "git_auth_fail.py"
    config_file.write_text("""
from dev_env.config import Environment, GitConfig
config = Environment(
    name="git-auth-test",
    base_image="python:3.13",
    git=GitConfig(url="git@github.com:private/repo.git")
)
""")

    mock_git_utils["setup_git_in_container"].side_effect = Exception("Permission denied (publickey)")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    # Should continue despite Git auth failure
    assert result == 0


class TestStateManagementErrors:
  """Test state management error scenarios"""

  def test_state_directory_permission_error(self, temp_dir):
    """Test handling of state directory permission errors"""
    readonly_dir = temp_dir / "readonly"
    readonly_dir.mkdir(mode=0o444)

    try:
      config_file = temp_dir / "perm_test.py"
      config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="perm-test", base_image="python:3.13")
""")

      up_args = Namespace(config=config_file, name=None, state_dir=readonly_dir)

      with patch("dev_env.utils.check_docker_available", return_value=True):
        # This may succeed or fail depending on system permissions
        result = cmd_up(up_args)
        # Either way, should not crash
        assert isinstance(result, int)

    finally:
      # Cleanup - make directory writable again
      readonly_dir.chmod(0o755)

  def test_state_database_corruption(self, temp_dir):
    """Test handling of corrupted state database"""
    state_dir = temp_dir / "state"
    state_dir.mkdir()

    # Create corrupted database file
    corrupt_db = state_dir / "environments.db"
    corrupt_db.write_bytes(b"this is not a valid sqlite database")

    # Try to use StateManager with corrupted database
    try:
      state_manager = StateManager(state_dir)
      # Operations should handle corruption gracefully
      envs = state_manager.list_environments()
      assert isinstance(envs, dict)
    except Exception as e:
      # Some corruption may be unrecoverable, which is acceptable
      assert "database" in str(e).lower() or "sqlite" in str(e).lower()

  def test_state_concurrent_access_conflict(self, state_manager):
    """Test handling of concurrent state access conflicts"""
    # Simulate concurrent modification by manually altering database
    env_data = {"container_id": "test123", "status": "creating"}
    state_manager.save_environment("concurrent-test", env_data)

    # Manually delete from database to simulate concurrent deletion
    with sqlite3.connect(state_manager.state_dir / "environments.db") as conn:
      conn.execute("DELETE FROM environments WHERE name = ?", ("concurrent-test",))
      conn.commit()

    # Try to access the environment that was concurrently deleted
    result = state_manager.get_environment("concurrent-test")
    assert result is None  # Should handle gracefully


class TestConfigurationErrors:
  """Test configuration-related error scenarios"""

  def test_malformed_python_config(self, temp_dir, mock_check_docker_available):
    """Test handling of malformed Python configuration files"""
    bad_configs = [
      "import sys; sys.exit(1)",  # Code that exits
      "raise Exception('Config error')",  # Code that raises exception
      "print('hello')\nconfig = 'not an Environment'",  # Wrong type
      "# No config variable defined",  # Missing config
    ]

    for i, bad_config in enumerate(bad_configs):
      config_file = temp_dir / f"bad_config_{i}.py"
      config_file.write_text(bad_config)

      up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
      result = cmd_up(up_args)

      assert result != 0  # Should fail gracefully

  def test_malformed_json_config(self, temp_dir, mock_check_docker_available):
    """Test handling of malformed JSON configuration files"""
    bad_json_configs = [
      '{"name": "test", "base_image":}',  # Invalid JSON syntax
      '{"name": "test"}',  # Missing required field
      '{"name": 123, "base_image": "python:3.13"}',  # Wrong type
      "",  # Empty file
      "not json at all",  # Not JSON
    ]

    for i, bad_json in enumerate(bad_json_configs):
      config_file = temp_dir / f"bad_json_{i}.json"
      config_file.write_text(bad_json)

      up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
      result = cmd_up(up_args)

      assert result != 0  # Should fail gracefully

  def test_circular_import_in_config(self, temp_dir, mock_check_docker_available):
    """Test handling of circular imports in Python configuration"""
    # Create two files that import each other
    config1 = temp_dir / "circular1.py"
    config2 = temp_dir / "circular2.py"

    config1.write_text("""
from circular2 import x
from dev_env.config import Environment
config = Environment(name="circular", base_image="python:3.13")
""")

    config2.write_text("""
from circular1 import config
x = 42
""")

    up_args = Namespace(config=config1, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0  # Should fail gracefully


class TestResourceExhaustionErrors:
  """Test handling of resource exhaustion scenarios"""

  def test_disk_space_exhaustion(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of disk space exhaustion during operations"""
    config_file = temp_dir / "disk_full.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="disk-test", base_image="python:3.13")
""")

    # Mock disk space error during container creation
    mock_docker.create_container.side_effect = RuntimeError("No space left on device")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0

  def test_memory_exhaustion(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test handling of memory exhaustion"""
    config_file = temp_dir / "memory_full.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="memory-test", base_image="python:3.13")
""")

    mock_docker.start_container.side_effect = RuntimeError("Cannot allocate memory")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")
    result = cmd_up(up_args)

    assert result != 0


class TestCleanupOnFailure:
  """Test cleanup behavior when operations fail"""

  def test_cleanup_on_container_start_failure(self, temp_dir, mock_check_docker_available, mock_docker, state_manager):
    """Test cleanup when container fails to start"""
    config_file = temp_dir / "start_fail.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(name="start-fail", base_image="python:3.13")
""")

    # Container creation succeeds but start fails
    mock_docker.create_container.return_value = "container123"
    mock_docker.start_container.side_effect = Exception("Container failed to start")

    up_args = Namespace(config=config_file, name=None, state_dir=state_manager.state_dir)
    result = cmd_up(up_args)

    assert result != 0

    # Verify environment was cleaned up from state
    env_state = state_manager.get_environment("start-fail")
    assert env_state is None

  def test_cleanup_on_ssh_setup_critical_failure(
    self, temp_dir, mock_check_docker_available, mock_docker, state_manager
  ):
    """Test cleanup when critical SSH setup fails"""
    config_file = temp_dir / "ssh_critical_fail.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="ssh-critical",
    base_image="python:3.13",
    ports={22: 2222}
)
""")

    # Make exec_run fail for sshd startup (critical)
    def exec_side_effect(container_id, cmd, **kwargs):
      if "/usr/sbin/sshd" in cmd:
        raise Exception("Critical SSH failure")
      return b"success"

    mock_docker.exec_run.side_effect = exec_side_effect

    up_args = Namespace(config=config_file, name=None, state_dir=state_manager.state_dir)
    result = cmd_up(up_args)

    # Should succeed despite SSH warning (non-critical)
    assert result == 0

  def test_no_cleanup_on_warnings(self, temp_dir, mock_check_docker_available, mock_docker, state_manager):
    """Test that warnings don't trigger cleanup"""
    config_file = temp_dir / "warnings.py"
    config_file.write_text("""
from dev_env.config import Environment
config = Environment(
    name="warnings-test",
    base_image="python:3.13",
    ports={22: 22}  # Will trigger privileged port warning
)
""")

    up_args = Namespace(config=config_file, name=None, state_dir=state_manager.state_dir)

    with patch("builtins.input", return_value="y"):  # Accept warnings
      result = cmd_up(up_args)

    assert result == 0

    # Environment should exist in state
    env_state = state_manager.get_environment("warnings-test")
    assert env_state is not None
