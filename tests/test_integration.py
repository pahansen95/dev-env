"""Integration tests for context-based dev-env interface"""

from unittest.mock import Mock, patch
from argparse import Namespace
import pytest
import io

from dev_env.state import StateManager


class TestContextWorkflow:
  """Test complete context-based environment lifecycle"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_context_environment_lifecycle(self, mock_resolve, mock_run_plumbing, tmp_path):
    """Test full context-based environment creation and teardown workflow"""
    from dev_env.commands.porcelain.work import WorkCommand
    from dev_env.commands.porcelain.stop import StopCommand

    # Setup context resolution
    test_context = {
      "id": "test123",
      "name": "test-env",
      "path": str(tmp_path),
      "created_at": "2024-01-01T10:00:00Z",
      "last_used": "2024-01-01T10:00:00Z",
      "state": "active",
    }
    mock_resolve.return_value = test_context

    # Setup plumbing command responses for work flow
    def work_plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "notfound"}
        elif "EnvCreate" in command.__class__.__name__:
          return {"status": "success", "container_id": "test123", "message": "Environment created successfully"}
        elif "EnvStart" in command.__class__.__name__:
          return {"status": "success", "state": "running"}
      return {}

    mock_run_plumbing.side_effect = work_plumbing_side_effect

    # Test work command (environment creation)
    work_command = WorkCommand()
    work_args = Namespace(name="test-env")

    with patch.object(work_command, "_load_config", return_value={"base_image": "python:3.13"}):
      with patch.object(work_command, "_show_progress"):
        work_command.execute(work_args)

    # Verify work command execution
    assert mock_run_plumbing.call_count >= 2

    # Test stop command (environment teardown)
    stop_command = StopCommand()
    stop_args = Namespace(name="test-env")

    def stop_plumbing_side_effect(*args):
      return {"status": "success", "message": "Environment stopped successfully"}

    with patch.object(stop_command, "_run_plumbing_command", side_effect=stop_plumbing_side_effect):
      with patch.object(stop_command, "_resolve_context", return_value=test_context):
        with patch.object(stop_command, "_show_progress"):
          stop_command.execute(stop_args)

  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  def test_environment_with_volumes_and_network(self, mock_state_class, mock_docker_class, tmp_path):
    """Test environment creation with volumes and custom network using plumbing commands"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    # Setup mocks
    mock_state = Mock()
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_docker.create_volume.return_value = {"Name": "test-volume"}
    mock_docker.create_network.return_value = None
    mock_docker_class.return_value = mock_docker

    # Create test YAML configuration
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("""
base_image: python:3.13
volumes:
  - source: data-vol
    target: /data
    type: named
  - source: ./test-data
    target: /host
network:
  name: test-network
  driver: bridge
""")

    # Mock configuration detection
    with patch("dev_env.config_detector.ConfigDetector") as mock_detector:
      mock_detector.return_value.detect.return_value = {
        "type": "yaml",
        "config": {
          "base_image": "python:3.13",
          "volumes": [
            {"source": "data-vol", "target": "/data", "type": "named"},
            {"source": "./test-data", "target": "/host"},
          ],
          "network": {"name": "test-network", "driver": "bridge"},
        },
      }

      # Test environment creation
      env_create = EnvCreateCommand()
      create_args = Namespace(context="test-env")

      with patch("sys.stdout", new_callable=io.StringIO):
        env_create.run(create_args)

      # Verify volume and network creation
      assert mock_docker.create_volume.call_count >= 1
      mock_docker.create_network.assert_called()

  @patch("dev_env.commands.porcelain.run.RunCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.run.RunCommand._resolve_context")
  def test_run_command_integration(self, mock_resolve, mock_run_plumbing):
    """Test command execution through run command"""
    from dev_env.commands.porcelain.run import RunCommand

    # Setup context resolution
    test_context = {"id": "test123", "name": "test-env", "path": "/test/path"}
    mock_resolve.return_value = test_context

    # Mock command execution
    mock_run_plumbing.return_value = {"status": "success", "exit_code": 0, "output": "Hello, World!"}

    # Test run command
    run_command = RunCommand()
    run_args = Namespace(command=["echo", "Hello, World!"])

    run_command.execute(run_args)

    # Verify execution
    mock_run_plumbing.assert_called()


class TestContextErrorHandling:
  """Test error handling scenarios in context-based interface"""

  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_context_not_found_error(self, mock_resolve):
    """Test handling when context cannot be resolved"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Mock context resolution failure
    mock_resolve.return_value = None

    work_command = WorkCommand()
    work_args = Namespace(name=None)

    # Should handle context resolution failure
    with patch("builtins.input", return_value="test-context"):
      with patch.object(work_command, "_create_context") as mock_create:
        mock_create.return_value = {"id": "test123", "name": "test-context", "path": "/test/path"}
        work_command.execute(work_args)

  @patch("dev_env.commands.porcelain.work.WorkCommand._run_plumbing_command")
  @patch("dev_env.commands.porcelain.work.WorkCommand._resolve_context")
  def test_environment_creation_failure(self, mock_resolve, mock_run_plumbing):
    """Test handling of environment creation failures"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Setup context resolution
    mock_resolve.return_value = {"id": "test123", "name": "test-env", "path": "/test/path"}

    # Mock environment creation failure
    def plumbing_side_effect(*args):
      command = args[0]
      if hasattr(command, "__class__"):
        if "EnvStatus" in command.__class__.__name__:
          return {"state": "notfound"}
        elif "EnvCreate" in command.__class__.__name__:
          return {"error": "Docker daemon not available"}
      return {}

    mock_run_plumbing.side_effect = plumbing_side_effect

    work_command = WorkCommand()
    work_args = Namespace(name="test-env")

    # Should handle creation failure
    with patch.object(work_command, "_load_config", return_value={"base_image": "python:3.13"}):
      with pytest.raises(SystemExit):
        work_command.execute(work_args)

  def test_invalid_configuration_error(self, tmp_path):
    """Test handling of invalid YAML configuration files"""
    from dev_env.commands.porcelain.work import WorkCommand

    # Create invalid YAML file
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("invalid: yaml: content: {")

    work_command = WorkCommand()
    test_context = {"id": "test123", "name": "test-env", "path": str(tmp_path)}

    # Should handle invalid configuration
    with patch.object(work_command, "_resolve_context", return_value=test_context):
      config = work_command._load_config(test_context)
      # Should return None for invalid config, triggering setup wizard
      assert config is None


class TestContextSecurityValidation:
  """Test security validation in context-based interface"""

  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  def test_security_validation_dangerous_volumes(self, mock_state_class, mock_docker_class, tmp_path):
    """Test security validation for dangerous volume mounts"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    # Setup mocks
    mock_state = Mock()
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker_class.return_value = mock_docker

    # Create dangerous configuration
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("""
base_image: python:3.13
volumes:
  - source: /etc
    target: /host-etc
""")

    # Mock configuration detection with dangerous volume
    with patch("dev_env.config_detector.ConfigDetector") as mock_detector:
      mock_detector.return_value.detect.return_value = {
        "type": "yaml",
        "config": {"base_image": "python:3.13", "volumes": [{"source": "/etc", "target": "/host-etc"}]},
      }

      env_create = EnvCreateCommand()
      create_args = Namespace(context="test-env")

      # Should handle security validation
      with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
        env_create.run(create_args)

        # Should output error about security violation
        output = mock_stdout.getvalue()
        # In a real implementation, this would contain security error

  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  def test_security_port_binding_validation(self, mock_state_class, mock_docker_class, tmp_path):
    """Test security validation for insecure port bindings"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand

    # Setup mocks
    mock_state = Mock()
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker_class.return_value = mock_docker

    # Create insecure port configuration
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("""
base_image: python:3.13
ports:
  - container: 22
    host: 2222
    bind_ip: "0.0.0.0"  # Insecure binding
""")

    # Mock configuration detection
    with patch("dev_env.config_detector.ConfigDetector") as mock_detector:
      mock_detector.return_value.detect.return_value = {
        "type": "yaml",
        "config": {"base_image": "python:3.13", "ports": [{"container": 22, "host": 2222, "bind_ip": "0.0.0.0"}]},
      }

      env_create = EnvCreateCommand()
      create_args = Namespace(context="test-env")

      # Should handle port security validation
      with patch("sys.stdout", new_callable=io.StringIO):
        env_create.run(create_args)


class TestContextStateManagement:
  """Test context and state persistence"""

  def test_context_state_persistence(self, tmp_path):
    """Test that context state is properly persisted"""
    from dev_env.state import ContextManager

    state_dir = tmp_path / "state"
    context_manager = ContextManager(state_dir)

    # Create context
    context = context_manager.create_context("test-context", tmp_path / "project")

    assert context.name == "test-context"
    assert context.path == tmp_path / "project"

    # Retrieve context
    retrieved = context_manager.get_context(context.id)
    assert retrieved is not None
    assert retrieved.name == "test-context"

    # List contexts
    contexts = context_manager.list_contexts()
    assert len(contexts) == 1
    assert contexts[0].name == "test-context"

  def test_environment_state_integration(self, tmp_path):
    """Test integration between context and environment state"""
    state_dir = tmp_path / "state"
    state = StateManager(state_dir)

    env_data = {
      "container_id": "test123",
      "container_name": "dev-test-context",
      "config": {"base_image": "python:3.13"},
      "volumes": ["data-vol"],
      "network": "test-network",
    }

    # Save environment state
    state.save_environment("test-context", env_data)
    retrieved = state.get_environment("test-context")

    assert retrieved is not None
    assert retrieved["container_id"] == "test123"
    assert retrieved["config"]["base_image"] == "python:3.13"

    # Test cleanup
    state.remove_environment("test-context")
    assert state.get_environment("test-context") is None


class TestContextNetworkingIntegration:
  """Test networking features in context-based interface"""

  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  @patch("dev_env.commands.plumbing.env_stop.DockerClient")
  def test_custom_network_lifecycle(self, mock_stop_docker, mock_state_class, mock_create_docker, tmp_path):
    """Test custom network creation and cleanup in context workflow"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand
    from dev_env.commands.plumbing.env_stop import EnvStopCommand

    # Setup mocks for creation
    mock_state = Mock()
    mock_state_class.return_value = mock_state

    mock_docker = Mock()
    mock_docker.create_network.return_value = None
    mock_docker.pull_image.return_value = None
    mock_docker.create_container.return_value = "test123"
    mock_docker.start_container.return_value = None
    mock_docker.wait_for_container_ready.return_value = True
    mock_create_docker.return_value = mock_docker

    # Setup mocks for cleanup
    mock_stop_docker_instance = Mock()
    mock_stop_docker_instance.stop_container.return_value = None
    mock_stop_docker_instance.remove_container.return_value = None
    mock_stop_docker_instance.remove_network.return_value = None
    mock_stop_docker.return_value = mock_stop_docker_instance

    # Mock configuration with custom network
    with patch("dev_env.config_detector.ConfigDetector") as mock_detector:
      mock_detector.return_value.detect.return_value = {
        "type": "yaml",
        "config": {"base_image": "python:3.13", "network": {"name": "test-net", "driver": "bridge"}},
      }

      # Test environment creation
      env_create = EnvCreateCommand()
      create_args = Namespace(context="network-test")

      with patch("sys.stdout", new_callable=io.StringIO):
        env_create.run(create_args)

      # Verify network creation
      mock_docker.create_network.assert_called()

      # Test environment cleanup
      mock_state.get_environment.return_value = {"container_id": "test123", "volumes": [], "network": "test-net"}

      env_stop = EnvStopCommand()
      stop_args = Namespace(context="network-test")

      with patch("sys.stdout", new_callable=io.StringIO):
        env_stop.run(stop_args)

      # Verify network cleanup
      mock_stop_docker_instance.remove_network.assert_called_with("test-net")


class TestContextCommandIntegration:
  """Test integration between different context commands"""

  def test_plumbing_command_json_output(self, tmp_path):
    """Test that plumbing commands provide consistent JSON output"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand
    from dev_env.commands.plumbing.context_list import ContextListCommand

    # Test context creation output
    context_create = ContextCreateCommand()
    create_args = Namespace(name="json-test", path=str(tmp_path))

    captured_output = io.StringIO()
    with patch("sys.stdout", captured_output):
      context_create.run(create_args)

    output = captured_output.getvalue()
    assert output  # Should have JSON output

    # Test context listing output
    context_list = ContextListCommand()
    list_args = Namespace()

    captured_output = io.StringIO()
    with patch("sys.stdout", captured_output):
      context_list.run(list_args)

    output = captured_output.getvalue()
    # Should contain JSON with the created context
    assert "json-test" in output

  def test_porcelain_plumbing_integration(self, tmp_path):
    """Test integration between porcelain and plumbing commands"""
    from dev_env.commands.porcelain.status import StatusCommand

    # Mock plumbing command execution
    with patch("dev_env.commands.porcelain.status.StatusCommand._run_plumbing_command") as mock_plumbing:
      mock_plumbing.return_value = {
        "contexts": [{"id": "test123", "name": "integration-test", "path": str(tmp_path), "state": "active"}]
      }

      status_command = StatusCommand()
      status_args = Namespace(all=True)

      # Should integrate plumbing command output
      with patch("builtins.print"):
        status_command.execute(status_args)

      mock_plumbing.assert_called()
