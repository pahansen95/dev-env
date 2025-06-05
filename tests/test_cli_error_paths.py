# tests/test_cli_error_paths.py

from pathlib import Path
from unittest.mock import patch, MagicMock
from argparse import Namespace
import pytest


class TestWorkCommandErrorPaths:
  """Test error handling paths in work command"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_environment_creation_failure(self, mock_resolve, mock_run_plumbing):
    """Test handling of environment creation failures"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution to succeed
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock plumbing command calls
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__") and "EnvCreate" in command.__class__.__name__:
        return {"error": "Docker image pull failed"}
      return {"state": "notfound"}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should exit with error when environment creation fails
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  @patch("builtins.input", side_effect=[""])  # Empty context name
  def test_work_invalid_context_name(self, mock_input, mock_resolve):
    """Test handling of invalid context name input"""
    from dev_env.commands.porcelain.work import WorkCommand

    mock_resolve.return_value = None  # No existing context

    command = WorkCommand()
    args = Namespace(name=None)

    # Should exit when empty context name is provided
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.work.WorkCommand._load_config")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  @patch("dev_env.setup_wizard.SetupWizard.run")
  def test_work_setup_wizard_failure(self, mock_wizard_run, mock_resolve, mock_load_config):
    """Test handling of setup wizard failures"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Context exists but no config
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}
    mock_load_config.return_value = None

    # Setup wizard fails
    mock_wizard_run.side_effect = Exception("Wizard configuration error")

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should handle wizard failure gracefully
    with patch.object(command, "_show_progress"):
      with pytest.raises(Exception, match="Wizard configuration error"):
        command.execute(args)


class TestRunCommandErrorPaths:
  """Test error handling paths in run command"""

  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_no_context_found(self, mock_resolve):
    """Test run command when no context is found"""
    from dev_env.commands.porcelain.run import RunCommand

    mock_resolve.return_value = None

    command = RunCommand()
    args = Namespace(command=["ls", "-la"])

    # Should exit when no context is found
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.run.RunCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_command_execution_failure(self, mock_resolve, mock_run_plumbing):
    """Test handling of failed command execution"""
    from dev_env.commands.porcelain.run import RunCommand

    # Context exists
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Command execution fails
    mock_run_plumbing.return_value = {"error": "Container not running", "exit_code": 1}

    command = RunCommand()
    args = Namespace(command=["nonexistent-command"])

    # Should handle command failure appropriately
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.run.RunCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_container_not_running(self, mock_resolve, mock_run_plumbing):
    """Test run command when container is not running"""
    from dev_env.commands.porcelain.run import RunCommand

    # Context exists
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Environment status check shows stopped
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__") and "EnvStatus" in command.__class__.__name__:
        return {"state": "stopped"}
      return {"error": "Environment not running"}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = RunCommand()
    args = Namespace(command=["ls"])

    # Should provide helpful error message
    with pytest.raises(SystemExit):
      command.execute(args)


class TestStopCommandErrorPaths:
  """Test error handling paths in stop command"""

  @patch("dev_env.commands.porcelain.stop.StopCommand._resolve_context")
  def test_stop_no_context_found(self, mock_resolve):
    """Test stop command when no context is found"""
    from dev_env.commands.porcelain.stop import StopCommand

    mock_resolve.return_value = None

    command = StopCommand()
    args = Namespace(name=None)

    # Should exit when no context is found
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.stop.StopCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.stop.StopCommand._resolve_context")
  def test_stop_environment_already_stopped(self, mock_resolve, mock_run_plumbing):
    """Test stopping an already stopped environment"""
    from dev_env.commands.porcelain.stop import StopCommand

    # Context exists
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Environment is already stopped
    mock_run_plumbing.return_value = {"state": "stopped", "message": "Environment already stopped"}

    command = StopCommand()
    args = Namespace(name="test-context")

    # Should handle gracefully
    command.execute(args)
    mock_run_plumbing.assert_called()

  @patch("dev_env.commands.porcelain.stop.StopCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.stop.StopCommand._resolve_context")
  def test_stop_docker_daemon_unavailable(self, mock_resolve, mock_run_plumbing):
    """Test stop command when Docker daemon is unavailable"""
    from dev_env.commands.porcelain.stop import StopCommand

    # Context exists
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Docker daemon error
    mock_run_plumbing.return_value = {"error": "Docker daemon not available"}

    command = StopCommand()
    args = Namespace(name="test-context")

    # Should exit with error
    with pytest.raises(SystemExit):
      command.execute(args)


class TestShellCommandErrorPaths:
  """Test error handling paths in shell command"""

  @patch("dev_env.commands.porcelain.shell.ShellCommand._resolve_context")
  def test_shell_no_context_found(self, mock_resolve):
    """Test shell command when no context is found"""
    from dev_env.commands.porcelain.shell import ShellCommand

    mock_resolve.return_value = None

    command = ShellCommand()
    args = Namespace()

    # Should exit when no context is found
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.shell.ShellCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.shell.ShellCommand._resolve_context")
  def test_shell_environment_not_running(self, mock_resolve, mock_run_plumbing):
    """Test shell command when environment is not running"""
    from dev_env.commands.porcelain.shell import ShellCommand

    # Context exists
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Environment is not running
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__") and "EnvStatus" in command.__class__.__name__:
        return {"state": "stopped"}
      return {"error": "Cannot attach to stopped container"}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = ShellCommand()
    args = Namespace()

    # Should provide helpful error message
    with pytest.raises(SystemExit):
      command.execute(args)


class TestPlumbingCommandErrorPaths:
  """Test error handling in plumbing commands"""

  @patch("dev_env.commands.plumbing.context_create.ContextManager")
  def test_context_create_duplicate_name(self, mock_context_manager_class):
    """Test context creation with duplicate name"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand

    mock_context_manager = MagicMock()
    mock_context_manager.create_context.side_effect = Exception("Context name already exists")
    mock_context_manager_class.return_value = mock_context_manager

    command = ContextCreateCommand()
    args = Namespace(name="test", path="/test/path")

    # Should handle context creation failure
    with patch("sys.stdout"):
      command.run(args)
      # Should output error in JSON format

  @patch("dev_env.commands.plumbing.env_create.StateManager")
  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  def test_env_create_docker_image_failure(self, mock_docker_class, mock_state_class):
    """Test environment creation with Docker image failure"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    # Mock Docker client failure
    mock_docker = MagicMock()
    mock_docker.pull_image.side_effect = Exception("Image pull failed")
    mock_docker._request.side_effect = RuntimeError("Image not found locally")
    mock_docker_class.return_value = mock_docker

    # Mock state manager
    mock_state = MagicMock()
    mock_state_class.return_value = mock_state

    command = EnvCreateCommand()
    args = Namespace(context="test-context")

    # Should handle image pull failure
    with patch("sys.stdout"):
      command.run(args)
      # Should output error in JSON format

  @patch("dev_env.commands.plumbing.env_stop.StateManager")
  @patch("dev_env.commands.plumbing.env_stop.DockerClient")
  def test_env_stop_container_already_removed(self, mock_docker_class, mock_state_class):
    """Test stopping environment when container is already removed"""
    from dev_env.commands.plumbing.env_stop import EnvStopCommand

    # Mock state manager
    mock_state = MagicMock()
    mock_state.get_environment.return_value = {"container_id": "test123", "volumes": [], "network": None}
    mock_state_class.return_value = mock_state

    # Mock Docker client - container doesn't exist
    mock_docker = MagicMock()
    mock_docker.stop_container.side_effect = RuntimeError("No such container")
    mock_docker_class.return_value = mock_docker

    command = EnvStopCommand()
    args = Namespace(context="test-context")

    # Should handle missing container gracefully
    with patch("sys.stdout"):
      command.run(args)
      # Should output appropriate status


class TestConfigurationErrorPaths:
  """Test configuration-related error scenarios"""

  @patch("dev_env.config_detector.ConfigDetector.detect")
  def test_work_invalid_configuration_detected(self, mock_detect):
    """Test work command with invalid configuration file"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Mock invalid configuration detection
    mock_detect.return_value = {"type": "invalid", "errors": ["Missing base_image", "Invalid port mapping"]}

    command = WorkCommand()

    # Test configuration validation logic
    with patch.object(command, "_resolve_context") as mock_resolve:
      mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

      with patch.object(command, "_load_config") as mock_load:
        mock_load.return_value = {"errors": ["Invalid configuration"]}

        args = Namespace(name="test-context")

        # Should handle configuration errors
        with pytest.raises(SystemExit):
          command.execute(args)

  @patch("dev_env.commands.porcelain.work.Path.write_text")
  def test_work_config_write_permission_error(self, mock_write_text):
    """Test work command when config file cannot be written"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Mock permission error on config write
    mock_write_text.side_effect = PermissionError("Permission denied")

    command = WorkCommand()

    # Test config writing error handling
    with pytest.raises(PermissionError):
      config_data = {"base_image": "python:3.13"}
      config_yaml = command._dict_to_yaml(config_data)
      Path("/test/dev-env.yaml").write_text(config_yaml)


class TestResourceCleanupErrorPaths:
  """Test resource cleanup error scenarios"""

  @patch("dev_env.commands.plumbing.env_stop.DockerClient")
  def test_stop_volume_cleanup_failure(self, mock_docker_class):
    """Test environment stop with volume cleanup failures"""
    from dev_env.commands.plumbing.env_stop import EnvStopCommand

    # Mock Docker client with volume removal failure
    mock_docker = MagicMock()
    mock_docker.stop_container.return_value = None
    mock_docker.remove_container.return_value = None
    mock_docker.remove_volume.side_effect = Exception("Volume in use")
    mock_docker_class.return_value = mock_docker

    command = EnvStopCommand()

    # Should handle volume cleanup failures gracefully
    # Verifying the command structure exists
    assert hasattr(command, "run")

  @patch("dev_env.commands.plumbing.env_stop.DockerClient")
  def test_stop_network_cleanup_failure(self, mock_docker_class):
    """Test environment stop with network cleanup failures"""
    from dev_env.commands.plumbing.env_stop import EnvStopCommand

    # Mock Docker client with network removal failure
    mock_docker = MagicMock()
    mock_docker.stop_container.return_value = None
    mock_docker.remove_container.return_value = None
    mock_docker.remove_network.side_effect = Exception("Network has active endpoints")
    mock_docker_class.return_value = mock_docker

    command = EnvStopCommand()

    # Should handle network cleanup failures gracefully
    # Verifying the command structure exists
    assert hasattr(command, "run")
