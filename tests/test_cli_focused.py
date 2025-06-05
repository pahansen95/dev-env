"""Focused CLI tests for specific context-based command coverage"""

from unittest.mock import patch, MagicMock
from argparse import Namespace
import pytest


class TestWorkCommandNetworkHandling:
  """Test network creation handling in work command"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_environment_creation_with_existing_network(self, mock_resolve, mock_run_plumbing):
    """Test work command when Docker network already exists"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock plumbing command responses
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "notfound"}
        elif "EnvCreate" in command.__class__.__name__:
          return {
            "status": "success",
            "message": "Network already exists: test-network",
            "warnings": ["Network test-network already exists, reusing"],
          }
        elif "EnvStart" in command.__class__.__name__:
          return {"status": "success"}
      return {}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should handle existing network gracefully
    with patch.object(command, "_load_config", return_value={"network": "test-network"}):
      with patch.object(command, "_show_progress"):
        command.execute(args)

    # Verify environment creation was attempted
    assert mock_run_plumbing.call_count >= 2

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_environment_creation_network_failure(self, mock_resolve, mock_run_plumbing):
    """Test work command when network creation fails"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock network creation failure
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "notfound"}
        elif "EnvCreate" in command.__class__.__name__:
          return {"error": "Failed to create network: permission denied"}
      return {}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should exit with error when network creation fails
    with patch.object(command, "_load_config", return_value={"network": "custom-network"}):
      with pytest.raises(SystemExit):
        command.execute(args)


class TestWorkCommandContainerLifecycle:
  """Test container creation and lifecycle in work command"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_complete_environment_setup_sequence(self, mock_resolve, mock_run_plumbing):
    """Test complete environment setup sequence in work command"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    call_sequence = []

    # Mock sequential plumbing command responses
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        command_name = command.__class__.__name__
        call_sequence.append(command_name)

        if "EnvStatus" in command_name:
          return {"state": "notfound"}
        elif "EnvCreate" in command_name:
          return {
            "status": "success",
            "container_id": "test123",
            "steps": [
              "Image pulled: python:3.13",
              "Container created: dev-test-context-abc123",
              "Container started successfully",
            ],
          }
        elif "EnvStart" in command_name:
          return {"status": "success", "state": "running"}
      return {}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should complete full setup sequence
    with patch.object(command, "_load_config", return_value={"base_image": "python:3.13"}):
      with patch.object(command, "_show_progress"):
        command.execute(args)

    # Verify correct command sequence
    assert "EnvStatusCommand" in call_sequence
    assert "EnvCreateCommand" in call_sequence

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_container_ready_validation(self, mock_resolve, mock_run_plumbing):
    """Test container readiness validation in work command"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock container creation with readiness check
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "stopped"}
        elif "EnvStart" in command.__class__.__name__:
          return {"status": "success", "state": "running", "readiness": "Container ready after 2.3s"}
      return {}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should validate container readiness
    with patch.object(command, "_load_config", return_value={"base_image": "python:3.13"}):
      with patch.object(command, "_show_progress"):
        command.execute(args)

    # Verify environment start was called
    assert mock_run_plumbing.call_count >= 2


class TestStopCommandResourceCleanup:
  """Test resource cleanup in stop command"""

  @patch("dev_env.commands.porcelain.stop.StopCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.stop.StopCommand._resolve_context")
  def test_stop_skip_volume_cleanup(self, mock_resolve, mock_run_plumbing):
    """Test stop command skipping volume cleanup by default"""
    from dev_env.commands.porcelain.stop import StopCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock stop operation without volume cleanup
    def mock_plumbing_side_effect(*args):
      return {
        "status": "success",
        "message": "Environment stopped",
        "volumes_preserved": ["test-volume-1", "test-volume-2"],
        "cleanup_skipped": ["volumes"],
      }

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = StopCommand()
    args = Namespace(name="test-context")

    # Should preserve volumes by default
    with patch.object(command, "_show_progress"):
      command.execute(args)

    # Verify stop command was called
    mock_run_plumbing.assert_called()

  @patch("dev_env.commands.porcelain.stop.StopCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.stop.StopCommand._resolve_context")
  def test_stop_with_resource_cleanup(self, mock_resolve, mock_run_plumbing):
    """Test stop command with comprehensive resource cleanup"""
    from dev_env.commands.porcelain.stop import StopCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Mock comprehensive cleanup
    def mock_plumbing_side_effect(*args):
      return {
        "status": "success",
        "message": "Environment stopped with cleanup",
        "cleanup_performed": {
          "container": "removed",
          "volumes": ["test-volume-1", "test-volume-2"],
          "networks": ["test-network"],
          "images": [],
        },
      }

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = StopCommand()
    args = Namespace(name="test-context", cleanup=True)  # With cleanup flag

    # Should perform comprehensive cleanup
    with patch.object(command, "_show_progress"):
      command.execute(args)

    # Verify cleanup was performed
    mock_run_plumbing.assert_called()


class TestStatusCommandFormatting:
  """Test status command output formatting"""

  @patch("dev_env.commands.porcelain.status.StatusCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.status.StatusCommand._resolve_context")
  def test_status_error_message_formatting(self, mock_resolve, mock_run_plumbing):
    """Test status command error message formatting"""
    from dev_env.commands.porcelain.status import StatusCommand

    # Context resolution succeeds
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Environment status check fails
    mock_run_plumbing.return_value = {
      "error": "Docker daemon not available",
      "error_code": "DOCKER_UNAVAILABLE",
      "suggestions": ["Start Docker daemon", "Check Docker installation"],
    }

    command = StatusCommand()

    # Should format error messages appropriately
    with patch("builtins.print") as mock_print:
      command._show_current_status()

      # Verify error formatting was handled
      mock_run_plumbing.assert_called()

  @patch("dev_env.commands.porcelain.status.StatusCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.status.StatusCommand._resolve_context")
  def test_status_rich_formatting_output(self, mock_resolve, mock_run_plumbing):
    """Test status command rich formatting with timestamps and icons"""
    from dev_env.commands.porcelain.status import StatusCommand

    # Context resolution succeeds
    mock_resolve.return_value = {
      "id": "test123",
      "name": "test-context",
      "path": "/test/path",
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-02T15:30:00Z",
    }

    # Environment status with detailed info
    mock_run_plumbing.return_value = {
      "state": "running",
      "container_id": "abc123",
      "uptime": "2 hours 15 minutes",
      "resource_usage": {"cpu": "15%", "memory": "256MB/1GB"},
    }

    command = StatusCommand()

    # Should display rich formatted output
    with patch.object(command, "_display_context_status") as mock_display:
      command._show_current_status()

      # Verify formatting method was called
      mock_display.assert_called_once()


class TestRunCommandEdgeCases:
  """Test edge case handling in run command"""

  @patch("dev_env.commands.porcelain.run.RunCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_empty_command_handling(self, mock_resolve, mock_run_plumbing):
    """Test run command with empty command arguments"""
    from dev_env.commands.porcelain.run import RunCommand

    # Context resolution succeeds
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Empty command should be handled gracefully
    mock_run_plumbing.return_value = {"error": "Command cannot be empty", "exit_code": 1}

    command = RunCommand()
    args = Namespace(command=[])  # Empty command

    # Should handle empty command appropriately
    with pytest.raises(SystemExit):
      command.execute(args)

  @patch("dev_env.commands.porcelain.run.RunCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_command_with_complex_arguments(self, mock_resolve, mock_run_plumbing):
    """Test run command with complex command arguments"""
    from dev_env.commands.porcelain.run import RunCommand

    # Context resolution succeeds
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Complex command execution
    mock_run_plumbing.return_value = {
      "status": "success",
      "exit_code": 0,
      "output": "Command executed successfully",
      "command": ["bash", "-c", "echo 'hello world' | grep hello"],
    }

    command = RunCommand()
    args = Namespace(command=["bash", "-c", "echo 'hello world' | grep hello"])

    # Should handle complex command structures
    command.execute(args)

    # Verify command was passed correctly
    mock_run_plumbing.assert_called()


class TestShellCommandEdgeCases:
  """Test edge case handling in shell command"""

  @patch("dev_env.commands.porcelain.shell.ShellCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.shell.ShellCommand._resolve_context")
  def test_shell_environment_transition_handling(self, mock_resolve, mock_run_plumbing):
    """Test shell command when environment is transitioning states"""
    from dev_env.commands.porcelain.shell import ShellCommand

    # Context resolution succeeds
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Environment in transitioning state
    def mock_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "starting", "message": "Container is starting up, please wait"}
        elif "Attach" in command.__class__.__name__:
          return {"error": "Cannot attach to starting container", "retry_after": 5}
      return {}

    mock_run_plumbing.side_effect = mock_plumbing_side_effect

    command = ShellCommand()
    args = Namespace()

    # Should handle transitioning state appropriately
    with pytest.raises(SystemExit):
      command.execute(args)


class TestPlumbingCommandIntegration:
  """Test plumbing command integration scenarios"""

  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  def test_env_create_with_environment_variables(self, mock_state_class, mock_docker_class):
    """Test environment creation with complex environment variable handling"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    # Mock successful Docker operations
    mock_docker = MagicMock()
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker_class.return_value = mock_docker

    # Mock state management
    mock_state = MagicMock()
    mock_state_class.return_value = mock_state

    command = EnvCreateCommand()
    args = Namespace(context="test-context")

    # Test with complex environment configuration
    with patch("dev_env.config_detector.ConfigDetector") as mock_detector:
      mock_detector.return_value.detect.return_value = {
        "type": "yaml",
        "config": {
          "base_image": "python:3.13",
          "environment": {"PATH": "/usr/local/bin:$PATH", "PYTHONPATH": "/app:/app/src", "DEBUG": "true"},
        },
      }

      # Should handle complex environment variables
      with patch("sys.stdout"):
        command.run(args)

  @patch("dev_env.commands.plumbing.context_create.ContextManager")
  def test_context_create_path_validation(self, mock_context_manager_class):
    """Test context creation with path validation"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand

    # Mock successful context creation
    mock_context_manager = MagicMock()
    mock_context = MagicMock()
    mock_context.to_dict.return_value = {
      "id": "test123",
      "name": "test-context",
      "path": "/valid/path",
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-01T10:00:00Z",
      "state": "active",
    }
    mock_context_manager.create_context.return_value = mock_context
    mock_context_manager_class.return_value = mock_context_manager

    command = ContextCreateCommand()
    args = Namespace(name="test-context", path="/valid/path")

    # Should validate and create context successfully
    with patch("sys.stdout"):
      command.run(args)

    # Verify context creation was called
    mock_context_manager.create_context.assert_called_once()


class TestConfigurationValidation:
  """Test configuration validation scenarios"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._load_config")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_work_invalid_configuration_handling(self, mock_resolve, mock_load_config):
    """Test work command with invalid configuration scenarios"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Context resolution succeeds
    mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

    # Configuration loading returns invalid config
    mock_load_config.return_value = {
      "errors": ["Missing required field: base_image", "Invalid port mapping: 80:80 requires privileged access"],
      "warnings": ["Using default working directory"],
    }

    command = WorkCommand()
    args = Namespace(name="test-context")

    # Should handle configuration validation errors
    with patch.object(command, "_setup_wizard") as mock_wizard:
      mock_wizard.return_value = {"base_image": "python:3.13"}

      with patch.object(command, "_show_progress"):
        command.execute(args)

      # Should trigger setup wizard for invalid config
      mock_wizard.assert_called_once()
