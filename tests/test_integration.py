"""Integration tests for environment lifecycle"""

from unittest.mock import patch
from argparse import Namespace

from dev_env.cli import cmd_up, cmd_down, cmd_list, cmd_exec, cmd_ssh, cmd_logs


class TestEnvironmentLifecycle:
  """Test complete environment lifecycle operations"""

  def test_up_down_lifecycle_minimal(
    self, temp_dir, mock_check_docker_available, mock_docker, mock_ssh_utils, mock_git_utils
  ):
    """Test basic up/down lifecycle with minimal configuration"""
    # Create minimal config file
    config_file = temp_dir / "minimal.py"
    config_file.write_text("""
from dev_env.config import Environment

config = Environment(
    name="minimal-env",
    base_image="python:3.13"
)
""")

    state_dir = temp_dir / "state"

    # Test up command
    up_args = Namespace(config=config_file, name=None, state_dir=state_dir)

    with patch("builtins.input", return_value="y"):  # Accept any warnings
      result = cmd_up(up_args)

    assert result == 0
    mock_docker.pull_image.assert_called_once()
    mock_docker.create_container.assert_called_once()
    mock_docker.start_container.assert_called_once()

    # Test down command
    down_args = Namespace(name="minimal-env", volumes=False, state_dir=state_dir)

    result = cmd_down(down_args)
    assert result == 0
    mock_docker.stop_container.assert_called_once()
    mock_docker.remove_container.assert_called_once()

  def test_up_down_lifecycle_full_config(
    self, sample_config_file, temp_dir, mock_check_docker_available, mock_docker, mock_ssh_utils, mock_git_utils
  ):
    """Test up/down lifecycle with full configuration including SSH and Git"""
    state_dir = temp_dir / "state"

    # Test up command with full config
    up_args = Namespace(config=sample_config_file, name=None, state_dir=state_dir)

    with patch("builtins.input", return_value="y"):
      result = cmd_up(up_args)

    assert result == 0

    # Verify Docker operations
    mock_docker.pull_image.assert_called_once()
    mock_docker.create_container.assert_called_once()
    mock_docker.start_container.assert_called_once()

    # Verify network creation
    mock_docker.create_network.assert_called_once()

    # Verify SSH setup (since port 22 is mapped)
    mock_ssh_utils["setup_ssh_server"].assert_called_once()
    mock_ssh_utils["inject_ssh_key"].assert_called_once()

    # Verify Git setup
    mock_git_utils["setup_git_in_container"].assert_called_once()

    # Test down command with volumes
    down_args = Namespace(name="test-env", volumes=True, state_dir=state_dir)

    result = cmd_down(down_args)
    assert result == 0

    # Verify cleanup
    mock_docker.stop_container.assert_called_once()
    mock_docker.remove_container.assert_called_once()
    mock_docker.remove_volume.assert_called()  # Should remove named volumes

  def test_environment_name_override(self, sample_config_file, temp_dir, mock_check_docker_available, mock_docker):
    """Test overriding environment name during creation"""
    state_dir = temp_dir / "state"

    up_args = Namespace(
      config=sample_config_file,
      name="custom-name",  # Override the name from config
      state_dir=state_dir,
    )

    with patch("builtins.input", return_value="y"):
      result = cmd_up(up_args)

    assert result == 0

    # Verify container was created with custom name
    create_call = mock_docker.create_container.call_args
    assert create_call[1]["name"] == "dev-env-custom-name"

  def test_environment_already_exists_error(
    self, sample_config_file, temp_dir, state_manager, mock_check_docker_available
  ):
    """Test error when trying to create environment that already exists"""
    # Pre-populate state with existing environment
    state_manager.save_environment("test-env", {"container_id": "existing123"})

    up_args = Namespace(config=sample_config_file, name=None, state_dir=state_manager.state_dir)

    result = cmd_up(up_args)
    assert result != 0  # Should fail with error

  def test_list_environments_integration(self, temp_dir, state_manager, mock_check_docker_available, mock_docker):
    """Test listing environments with real state data"""
    # Create some test environments in state
    state_manager.save_environment(
      "env1",
      {"container_id": "container1", "config": {"base_image": "python:3.13"}, "volumes": ["vol1"], "network": "net1"},
    )

    state_manager.save_environment(
      "env2", {"container_id": "container2", "config": {"base_image": "node:18"}, "volumes": [], "network": None}
    )

    # Mock container status responses
    def mock_get_container(container_id):
      if container_id == "container1":
        return {"State": {"Status": "running"}}
      elif container_id == "container2":
        return {"State": {"Status": "exited"}}

    mock_docker.get_container.side_effect = mock_get_container

    list_args = Namespace(state_dir=state_manager.state_dir)

    with patch("sys.stdout") as mock_stdout:
      result = cmd_list(list_args)

    assert result == 0
    # Verify both environments appear in output
    output_calls = mock_stdout.write.call_args_list
    output_text = "".join(call[0][0] for call in output_calls)
    assert "env1" in output_text
    assert "env2" in output_text
    assert "running" in output_text
    assert "exited" in output_text


class TestCommandExecution:
  """Test command execution in environments"""

  def test_exec_command_success(self, temp_dir, state_manager, mock_check_docker_available, mock_docker):
    """Test successful command execution"""
    # Setup environment state
    state_manager.save_environment(
      "test-env", {"container_id": "container123", "config": {"base_image": "python:3.13"}}
    )

    # Mock container as running
    mock_docker.get_container.return_value = {"State": {"Status": "running"}}
    mock_docker.create_exec.return_value = "exec123"
    mock_docker.start_exec.return_value = b"command output"
    mock_docker.get_exec_info.return_value = {"ExitCode": 0}

    exec_args = Namespace(name="test-env", command=["ls", "-la"], state_dir=state_manager.state_dir)

    with patch("sys.stdout"):
      result = cmd_exec(exec_args)

    assert result == 0
    mock_docker.create_exec.assert_called_once_with(
      container_id="container123", cmd=["ls", "-la"], tty=True, attach_stdout=True, attach_stderr=True
    )

  def test_exec_command_container_not_running(self, temp_dir, state_manager, mock_check_docker_available, mock_docker):
    """Test exec command when container is not running"""
    state_manager.save_environment(
      "stopped-env", {"container_id": "container456", "config": {"base_image": "python:3.13"}}
    )

    # Mock container as stopped
    mock_docker.get_container.return_value = {"State": {"Status": "exited"}}

    exec_args = Namespace(name="stopped-env", command=["ls"], state_dir=state_manager.state_dir)

    result = cmd_exec(exec_args)
    assert result != 0  # Should fail

  def test_ssh_command_integration(self, temp_dir, state_manager, mock_subprocess):
    """Test SSH command integration"""
    # Setup environment with SSH enabled
    state_manager.save_environment(
      "ssh-env", {"container_id": "container789", "config": {"base_image": "ubuntu:22.04", "ports": {"22": 2222}}}
    )

    ssh_args = Namespace(name="ssh-env", ssh_args=["-v"], state_dir=state_manager.state_dir)

    result = cmd_ssh(ssh_args)
    assert result == 0

    # Verify SSH was called with correct arguments
    mock_subprocess["call"].assert_called_once()
    call_args = mock_subprocess["call"].call_args[0][0]
    assert "ssh" in call_args
    assert "-p" in call_args
    assert "2222" in call_args
    assert "-v" in call_args
    assert "root@localhost" in call_args

  def test_logs_command_integration(self, temp_dir, state_manager, mock_check_docker_available, mock_docker):
    """Test logs command integration"""
    state_manager.save_environment(
      "log-env", {"container_id": "container_logs", "config": {"base_image": "python:3.13"}}
    )

    mock_docker.get_container_logs.return_value = b"container log output\n"

    logs_args = Namespace(name="log-env", follow=False, tail=None, state_dir=state_manager.state_dir)

    with patch("sys.stdout"):
      result = cmd_logs(logs_args)

    assert result == 0
    mock_docker.get_container_logs.assert_called_once_with(container_id="container_logs", follow=False, tail=None)


class TestErrorScenarios:
  """Test error handling in integration scenarios"""

  def test_up_command_docker_unavailable(self, sample_config_file, temp_dir, mock_docker_unavailable):
    """Test up command when Docker is not available"""
    up_args = Namespace(config=sample_config_file, name=None, state_dir=temp_dir / "state")

    result = cmd_up(up_args)
    assert result != 0  # Should fail

  def test_up_command_image_pull_failure(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test up command when image pull fails"""
    # Create config with non-existent image
    config_file = temp_dir / "bad_image.py"
    config_file.write_text("""
from dev_env.config import Environment

config = Environment(
    name="bad-image-env",
    base_image="nonexistent:latest"
)
""")

    # Mock image pull failure and no local image
    mock_docker.pull_image.side_effect = Exception("404 Not Found")
    mock_docker._request.side_effect = RuntimeError("No such image")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")

    result = cmd_up(up_args)
    assert result != 0  # Should fail

  def test_down_command_environment_not_found(self, temp_dir, mock_check_docker_available):
    """Test down command with non-existent environment"""
    down_args = Namespace(name="nonexistent-env", volumes=False, state_dir=temp_dir / "state")

    result = cmd_down(down_args)
    assert result != 0  # Should fail

  def test_up_command_with_user_confirmation(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test up command with warnings requiring user confirmation"""
    # Create config with privileged ports (will trigger warnings)
    config_file = temp_dir / "privileged.py"
    config_file.write_text("""
from dev_env.config import Environment

config = Environment(
    name="privileged-env",
    base_image="python:3.13",
    ports={22: 22, 80: 80}  # Privileged ports
)
""")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")

    # Test user says no
    with patch("builtins.input", return_value="n"):
      result = cmd_up(up_args)
    assert result == 1  # Should abort

    # Test user says yes
    with patch("builtins.input", return_value="y"):
      result = cmd_up(up_args)
    assert result == 0  # Should proceed

  def test_network_cleanup_with_other_containers(
    self, temp_dir, mock_check_docker_available, mock_docker, state_manager
  ):
    """Test network cleanup when other containers are using the network"""
    # Setup environment with custom network
    state_manager.save_environment(
      "net-env", {"container_id": "container_net", "config": {"base_image": "python:3.13"}, "network": "shared-network"}
    )

    # Mock network with other containers attached
    mock_docker.get_network.return_value = {
      "Name": "shared-network",
      "Containers": {"other_container": {"Name": "other-app"}},
    }

    down_args = Namespace(name="net-env", volumes=False, state_dir=state_manager.state_dir)

    result = cmd_down(down_args)
    assert result == 0

    # Verify network was NOT removed (other containers using it)
    mock_docker.remove_network.assert_not_called()

  def test_configuration_file_not_found(self, temp_dir, mock_check_docker_available):
    """Test up command with non-existent configuration file"""
    nonexistent_config = temp_dir / "missing.py"

    up_args = Namespace(config=nonexistent_config, name=None, state_dir=temp_dir / "state")

    result = cmd_up(up_args)
    assert result == 1  # Should fail

  def test_invalid_configuration_syntax(self, temp_dir, mock_check_docker_available):
    """Test up command with invalid Python configuration"""
    invalid_config = temp_dir / "invalid.py"
    invalid_config.write_text("invalid python syntax {}")

    up_args = Namespace(config=invalid_config, name=None, state_dir=temp_dir / "state")

    result = cmd_up(up_args)
    assert result == 1  # Should fail


class TestStateConsistency:
  """Test state consistency across operations"""

  def test_state_persistence_across_operations(
    self, sample_config_file, temp_dir, mock_check_docker_available, mock_docker
  ):
    """Test that state is properly maintained across multiple operations"""
    state_dir = temp_dir / "state"

    # Create environment
    up_args = Namespace(config=sample_config_file, name=None, state_dir=state_dir)

    with patch("builtins.input", return_value="y"):
      result = cmd_up(up_args)
    assert result == 0

    # Verify state was saved
    from dev_env.state import StateManager

    state_manager = StateManager(state_dir)
    env_state = state_manager.get_environment("test-env")
    assert env_state is not None
    assert "container_id" in env_state

    # List environments should show the created environment
    list_args = Namespace(state_dir=state_dir)
    with patch("sys.stdout"):
      result = cmd_list(list_args)
    assert result == 0

    # Remove environment
    down_args = Namespace(name="test-env", volumes=True, state_dir=state_dir)

    result = cmd_down(down_args)
    assert result == 0

    # Verify state was cleaned up
    env_state = state_manager.get_environment("test-env")
    assert env_state is None

  def test_partial_failure_cleanup(self, temp_dir, mock_check_docker_available, mock_docker):
    """Test cleanup when environment creation partially fails"""
    config_file = temp_dir / "test.py"
    config_file.write_text("""
from dev_env.config import Environment

config = Environment(
    name="partial-fail",
    base_image="python:3.13"
)
""")

    # Mock failure after container creation
    mock_docker.create_container.return_value = "container123"
    mock_docker.start_container.side_effect = Exception("Failed to start")

    up_args = Namespace(config=config_file, name=None, state_dir=temp_dir / "state")

    result = cmd_up(up_args)
    assert result != 0  # Should fail

    # Verify state was cleaned up (environment should not exist)
    from dev_env.state import StateManager

    state_manager = StateManager(temp_dir / "state")
    env_state = state_manager.get_environment("partial-fail")
    assert env_state is None
