"""Integration tests for context-based dev-env interface - consolidated version"""

from unittest.mock import MagicMock, patch
from argparse import Namespace
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
        stop_command.execute(stop_args)

  @patch("dev_env.commands.plumbing.env_create.generate_container_name")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  @patch("dev_env.commands.plumbing.env_create.load_environment")
  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.ContextResolver")
  @patch("dev_env.commands.plumbing.env_create.ContextManager")
  def test_environment_with_volumes_and_network(
    self,
    mock_cm_class,
    mock_resolver_class,
    mock_docker_class,
    mock_load_env,
    mock_state_class,
    mock_gen_name,
    tmp_path,
  ):
    """Test environment creation with custom volumes and network - FIXED"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand
    from dev_env.config import Environment, VolumeMount

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
""")

    # Setup context
    mock_context = MagicMock()
    mock_context.id = "test123"
    mock_context.name = "test-env"
    mock_context.path = tmp_path

    # Setup mocks
    mock_cm = MagicMock()
    mock_cm_class.return_value = mock_cm

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = mock_context
    mock_resolver_class.return_value = mock_resolver

    # Mock Docker client
    mock_docker = MagicMock()
    mock_docker.inspect_container.side_effect = Exception("Container not found")  # Container doesn't exist
    mock_docker.create_container.return_value = {"Id": "container123"}
    mock_docker_class.return_value = mock_docker

    # Mock configuration
    test_config = Environment(
      name="test-env",
      base_image="python:3.13",
      volumes=[VolumeMount(source="data-vol", target="/data"), VolumeMount(source="./test-data", target="/host")],
    )
    mock_load_env.return_value = test_config

    # Mock state manager
    mock_state = MagicMock()
    mock_state_class.return_value = mock_state

    # Mock container name generation
    mock_gen_name.return_value = "dev-test-env-abc123"

    # Test environment creation
    env_create = EnvCreateCommand()
    create_args = Namespace(context="test-env")

    with patch("sys.stdout", new_callable=io.StringIO):
      env_create.run(create_args)

    # Verify container creation was called
    assert mock_docker.create_container.called
    assert mock_docker.create_container.call_args[1]["name"] == "dev-test-env-abc123"
    assert mock_docker.create_container.call_args[1]["image"] == "python:3.13"

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
      with patch.object(work_command, "_load_config", return_value={"base_image": "python:3.13"}):
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
      exit_code = work_command.execute(work_args)

      # Should return non-zero exit code on failure
      assert exit_code != 0

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
      # Should return config object with path even if YAML is invalid
      assert config is not None
      assert config["path"] == str(config_file)


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

  @patch("dev_env.commands.plumbing.env_stop.StateManager")
  @patch("dev_env.commands.plumbing.env_stop.ContextManager")
  @patch("dev_env.commands.plumbing.env_create.generate_container_name")
  @patch("dev_env.commands.plumbing.env_create.StateManager")
  @patch("dev_env.commands.plumbing.env_stop.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.load_environment")
  @patch("dev_env.commands.plumbing.env_create.DockerClient")
  @patch("dev_env.commands.plumbing.env_create.ContextResolver")
  @patch("dev_env.commands.plumbing.env_create.ContextManager")
  def test_custom_network_lifecycle(
    self,
    mock_cm_class,
    mock_resolver_class,
    mock_create_docker_class,
    mock_load_env,
    mock_stop_docker_class,
    mock_state_class,
    mock_gen_name,
    mock_stop_cm_class,
    mock_stop_state_class,
    tmp_path,
  ):
    """Test custom network creation and cleanup - FIXED"""
    from dev_env.commands.plumbing.env_create import EnvCreateCommand
    from dev_env.commands.plumbing.env_stop import EnvStopCommand
    from dev_env.config import Environment

    # Create test YAML
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("""
base_image: python:3.13
network:
  name: test-net
  driver: bridge
""")

    # Setup context
    from dev_env.context import Context

    mock_context = MagicMock(spec=Context)
    # Configure all attributes that will be accessed
    mock_context.configure_mock(id="test456", name="network-test", state="active")
    mock_context.path = tmp_path

    # Setup context manager and resolver
    mock_cm = MagicMock()
    mock_cm_class.return_value = mock_cm

    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = mock_context
    mock_resolver_class.return_value = mock_resolver

    # Mock Docker client for creation
    mock_docker = MagicMock()
    mock_docker.inspect_container.side_effect = Exception("Container not found")
    mock_docker.create_container.return_value = {"Id": "container456"}
    mock_create_docker_class.return_value = mock_docker

    # Mock configuration
    test_config = Environment(name="network-test", base_image="python:3.13")
    mock_load_env.return_value = test_config

    # Mock state manager for creation
    mock_state = MagicMock()
    mock_state_class.return_value = mock_state

    # Mock container name
    mock_gen_name.return_value = "dev-network-test-xyz789"

    # Test environment creation
    env_create = EnvCreateCommand()
    create_args = Namespace(context="network-test")

    with patch("sys.stdout", new_callable=io.StringIO):
      env_create.run(create_args)

    # Verify container creation
    assert mock_docker.create_container.called

    # Setup mocks for stop command
    mock_stop_cm = MagicMock()
    mock_stop_cm.state_dir = tmp_path / "state"
    mock_stop_cm_class.return_value = mock_stop_cm

    # Mock stop context resolver
    with patch("dev_env.commands.plumbing.env_stop.ContextResolver") as mock_stop_resolver_class:
      mock_stop_resolver = MagicMock()
      mock_stop_resolver.resolve.return_value = mock_context
      mock_stop_resolver_class.return_value = mock_stop_resolver

      mock_stop_docker = MagicMock()
      mock_stop_docker.inspect_container.return_value = {"State": {"Running": True}}
      mock_stop_docker.stop_container.return_value = None
      mock_stop_docker.remove_container.return_value = None
      mock_stop_docker.remove_network.return_value = None
      mock_stop_docker.remove_volume.return_value = None
      mock_stop_docker_class.return_value = mock_stop_docker

      # Mock stop state manager
      mock_stop_state = MagicMock()
      mock_stop_state_class.return_value = mock_stop_state
      mock_stop_state.get_environment.return_value = {
        "container_id": "container456",
        "volumes": [],
        "network": "test-net",
      }

      # Test environment cleanup
      env_stop = EnvStopCommand()
      stop_args = Namespace(context="network-test")

      with patch("sys.stdout", new_callable=io.StringIO):
        env_stop.run(stop_args)

      # Verify all cleanup operations
      mock_stop_docker.stop_container.assert_called_with("container456")
      mock_stop_docker.remove_container.assert_called_with("container456")
      mock_stop_docker.remove_network.assert_called_with("test-net")
      mock_stop_state.remove_environment.assert_called_with("network-test")

      # Verify context state update
      assert mock_context.state == "inactive"
      mock_stop_cm.update_context.assert_called_with(mock_context)


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
