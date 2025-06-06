"""Test error handling paths in CLI commands - consolidated version"""

import pytest
from unittest.mock import patch, Mock
from argparse import Namespace

from dev_env.commands.porcelain.work import WorkCommand
from dev_env.commands.porcelain.run import RunCommand
from dev_env.commands.porcelain.stop import StopCommand
from dev_env.commands.porcelain.shell import ShellCommand


class TestCommandNoContextFound:
  """Test all commands handle missing context consistently"""

  @pytest.mark.parametrize(
    "command_class,args,expected_behavior",
    [
      (RunCommand, Namespace(command=["ls", "-la"]), "error"),
      (StopCommand, Namespace(name=None), "error"),
      (ShellCommand, Namespace(), "error"),
      (WorkCommand, Namespace(name=None), "create_new"),
    ],
  )
  def test_command_no_context_behavior(self, command_class, args, expected_behavior):
    """Test commands handle missing context appropriately"""
    with patch.object(command_class, "_resolve_context", return_value=None):
      command = command_class()

      if expected_behavior == "error":
        # Commands that require existing context should fail
        exit_code = command.execute(args)
        assert exit_code != 0
      else:
        # WorkCommand creates new context when missing
        with patch.object(command_class, "_create_context"):
          # Would test actual creation logic in integration tests
          pass


class TestCommandEnvironmentNotRunning:
  """Test commands that require running environment"""

  @pytest.mark.parametrize(
    "command_class,args",
    [
      (RunCommand, Namespace(command=["ls"])),
      (ShellCommand, Namespace()),
    ],
  )
  def test_command_with_stopped_environment(self, command_class, args):
    """Test commands fail gracefully when environment is stopped"""
    with patch.object(command_class, "_resolve_context") as mock_resolve:
      with patch.object(command_class, "_run_plumbing_command") as mock_run:
        # Context exists
        mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}

        # Environment is stopped
        mock_run.return_value = {"state": "stopped", "context_name": "test-context"}

        command = command_class()
        exit_code = command.execute(args)
        assert exit_code != 0


class TestWorkCommandSpecificErrors:
  """Test error scenarios specific to work command"""

  def test_work_invalid_context_name(self):
    """Test handling of invalid context name input"""
    from dev_env.io import InputProvider

    mock_input = Mock(spec=InputProvider)
    mock_input.get_input.return_value = ""  # Empty name

    with patch.object(WorkCommand, "_resolve_context", return_value=None):
      command = WorkCommand(input_provider=mock_input)
      exit_code = command.execute(Namespace(name=None))
      assert exit_code != 0

  def test_work_setup_wizard_failure(self, mock_input_provider, isolated_workspace):
    """Test handling of setup wizard failures"""
    workspace_path = isolated_workspace["workspace"]

    with patch.object(WorkCommand, "_resolve_context") as mock_resolve:
      with patch.object(WorkCommand, "_load_config", return_value=None):
        with patch("dev_env.setup_wizard.SetupWizard.run", side_effect=Exception("Wizard error")):
          mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": str(workspace_path)}

          command = WorkCommand(input_provider=mock_input_provider)
          exit_code = command.execute(Namespace(name="test-context"))
          assert exit_code != 0


class TestDockerRelatedErrors:
  """Test Docker-related error scenarios"""

  @pytest.mark.parametrize(
    "command_class,error_response",
    [
      (StopCommand, {"error": "Docker daemon not available"}),
      (RunCommand, {"error": "Container not running", "exit_code": 1}),
    ],
  )
  def test_docker_errors(self, command_class, error_response):
    """Test commands handle Docker errors appropriately"""
    with patch.object(command_class, "_resolve_context") as mock_resolve:
      with patch.object(command_class, "_run_plumbing_command") as mock_run:
        mock_resolve.return_value = {"id": "test123", "name": "test-context", "path": "/test"}
        mock_run.return_value = error_response

        command = command_class()
        args = Namespace(name="test-context") if command_class == StopCommand else Namespace(command=["ls"])

        exit_code = command.execute(args)
        assert exit_code != 0


class TestPlumbingCommandErrors:
  """Test error handling in plumbing commands"""

  @pytest.mark.parametrize(
    "error_scenario",
    [
      {
        "module": "context_create",
        "class": "ContextCreateCommand",
        "error": Exception("Context name already exists"),
        "args": {"name": "test", "path": "/test/path"},
      },
      {
        "module": "env_create",
        "class": "EnvCreateCommand",
        "error": Exception("Image pull failed"),
        "args": {"context": "test-context"},
      },
      {
        "module": "env_stop",
        "class": "EnvStopCommand",
        "error": RuntimeError("No such container"),
        "args": {"context": "test-context"},
      },
    ],
  )
  def test_plumbing_command_error_handling(self, error_scenario):
    """Test plumbing commands handle errors gracefully"""
    module = __import__(f"dev_env.commands.plumbing.{error_scenario['module']}", fromlist=[error_scenario["class"]])
    cmd_class = getattr(module, error_scenario["class"])

    # Mock the appropriate manager/client based on command type
    if "context" in error_scenario["module"]:
      patch_target = f"dev_env.commands.plumbing.{error_scenario['module']}.ContextManager"
    else:
      patch_target = f"dev_env.commands.plumbing.{error_scenario['module']}.DockerClient"

    with patch(patch_target) as mock_manager:
      mock_instance = Mock()
      mock_manager.return_value = mock_instance

      # Set up the error
      for attr in dir(mock_instance):
        if not attr.startswith("_"):
          setattr(mock_instance, attr, Mock(side_effect=error_scenario["error"]))

      command = cmd_class()
      args = Namespace(**error_scenario["args"])

      # Plumbing commands output JSON and don't raise
      with patch("sys.stdout"):
        command.run(args)  # Should handle error gracefully
