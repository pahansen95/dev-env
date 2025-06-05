# tests/test_docker_integration.py

import time
import pytest
from dev_env.docker import DockerClient
from dev_env.utils import check_docker_available


@pytest.mark.integration
@pytest.mark.skipif(not check_docker_available(), reason="Docker not available")
class TestDockerRealIntegration:
  """Real Docker integration tests - run against actual Docker daemon"""

  @pytest.fixture
  def docker_client(self):
    """Provide real Docker client"""
    return DockerClient()

  @pytest.fixture
  def test_container_name(self):
    """Generate unique container name for testing"""
    import time

    return f"test-devenv-{int(time.time())}"

  @pytest.fixture(autouse=True)
  def cleanup_containers(self, docker_client, test_container_name):
    """Ensure test containers are cleaned up"""
    yield
    # Cleanup after test
    try:
      containers = docker_client.list_containers(all=True)
      for container in containers:
        if container.get("Names", [""])[0].startswith("/test-devenv-"):
          docker_client.remove_container(container["Id"], force=True)
    except Exception:
      pass

  def test_minimal_container_lifecycle(self, docker_client, test_container_name):
    """Test basic container operations with real Docker"""
    # Use a small, fast image for testing
    test_image = "alpine:latest"

    # Pull image if needed
    docker_client.pull_image(test_image)

    # Create container
    container_id = docker_client.create_container(name=test_container_name, image=test_image, command=["sleep", "300"])
    assert container_id

    # Start container
    docker_client.start_container(container_id)

    # Verify running
    container = docker_client.get_container(container_id)
    assert container["State"]["Status"] == "running"

    # Execute command
    output, exit_code = docker_client.exec_run(container_id, ["echo", "hello from test"])
    assert exit_code == 0
    assert b"hello from test" in output

    # Stop container
    docker_client.stop_container(container_id)

    # Verify stopped
    container = docker_client.get_container(container_id)
    assert container["State"]["Status"] != "running"

    # Remove container
    docker_client.remove_container(container_id)

  def test_volume_operations(self, docker_client):
    """Test volume creation and usage"""
    volume_name = f"test-vol-{int(time.time())}"

    try:
      # Create volume
      volume = docker_client.create_volume(volume_name, labels={"test": "true"})
      assert volume["Name"] == volume_name

      # List volumes and verify
      volumes = docker_client.list_volumes()
      volume_names = [v["Name"] for v in volumes]
      assert volume_name in volume_names

    finally:
      # Cleanup
      try:
        docker_client.remove_volume(volume_name)
      except Exception:
        pass

  def test_network_operations(self, docker_client, test_container_name):
    """Test custom network creation and container connection"""
    network_name = f"test-net-{int(time.time())}"

    try:
      # Create network
      docker_client.create_network(network_name, driver="bridge", labels={"test": "true"})

      # Create container on custom network
      container_id = docker_client.create_container(
        name=test_container_name, image="alpine:latest", network=network_name, command=["sleep", "300"]
      )

      docker_client.start_container(container_id)

      # Verify network connection
      container = docker_client.get_container(container_id)
      networks = container.get("NetworkSettings", {}).get("Networks", {})
      assert network_name in networks

      docker_client.stop_container(container_id)
      docker_client.remove_container(container_id)

    finally:
      # Cleanup
      try:
        docker_client.remove_network(network_name)
      except Exception:
        pass


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skipif(not check_docker_available(), reason="Docker not available")
class TestEndToEndWorkflow:
  """Complete end-to-end workflow tests using context-based commands"""

  @pytest.fixture
  def test_config_file(self, tmp_path):
    """Create test YAML configuration file"""
    config_file = tmp_path / "dev-env.yaml"
    config_file.write_text("""
base_image: python:3.13-alpine
command: ["sleep", "infinity"]
volumes:
  - source: test-data
    target: /data
    type: named
ports:
  - container: 8080
    host: 18080
environment:
  TEST_VAR: test_value
working_directory: /workspace
""")
    return config_file

  @pytest.fixture
  def test_context(self, tmp_path):
    """Create test context directory"""
    context_dir = tmp_path / "test-project"
    context_dir.mkdir()

    # Create dev-env directory marker
    dev_env_dir = context_dir / ".dev-env"
    dev_env_dir.mkdir()

    return context_dir

  def test_complete_context_workflow(self, test_config_file, test_context, tmp_path):
    """Test complete workflow using context-based commands"""
    from dev_env.commands.porcelain.work import WorkCommand
    from dev_env.commands.porcelain.run import RunCommand
    from dev_env.commands.porcelain.stop import StopCommand
    from dev_env.commands.plumbing.context_create import ContextCreateCommand
    from argparse import Namespace
    import os

    # Setup test context
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Copy config file to context directory
    config_dest = test_context / "dev-env.yaml"
    config_dest.write_text(test_config_file.read_text())

    # Create context
    context_create = ContextCreateCommand()
    context_args = Namespace(name="e2e-test", path=str(test_context))

    # Change to context directory for commands
    original_cwd = os.getcwd()

    try:
      os.chdir(test_context)

      # Create context using plumbing command
      with pytest.MonkeyPatch().context() as mp:
        mp.setenv("DEV_ENV_STATE_DIR", str(state_dir))
        context_create.run(context_args)

      # Start environment using work command
      work_command = WorkCommand()
      work_args = Namespace(name="e2e-test")

      # Mock the interactive portions of work command
      with pytest.MonkeyPatch().context() as mp:
        mp.setenv("DEV_ENV_STATE_DIR", str(state_dir))

        # Mock the work command execution to avoid interactive wizard
        def mock_load_config(self, context):
          return {"path": str(config_dest)}

        def mock_get_status(self, context):
          return {"state": "notfound"}

        def mock_create_environment(self, context, config):
          # Simulate successful environment creation
          pass

        def mock_show_ready_message(self, context):
          pass

        mp.setattr(WorkCommand, "_load_config", mock_load_config)
        mp.setattr(WorkCommand, "_get_status", mock_get_status)
        mp.setattr(WorkCommand, "_create_environment", mock_create_environment)
        mp.setattr(WorkCommand, "_show_ready_message", mock_show_ready_message)

        work_command.execute(work_args)

      # Execute command using run command
      run_command = RunCommand()
      run_args = Namespace(command=["echo", "test_value"])

      with pytest.MonkeyPatch().context() as mp:
        mp.setenv("DEV_ENV_STATE_DIR", str(state_dir))

        def mock_run_plumbing_command(self, command, args):
          # Mock successful command execution
          return {"status": "success", "exit_code": 0, "output": "test_value"}

        mp.setattr(RunCommand, "_run_plumbing_command", mock_run_plumbing_command)

        run_command.execute(run_args)

      # Stop environment using stop command
      stop_command = StopCommand()
      stop_args = Namespace(name="e2e-test")

      with pytest.MonkeyPatch().context() as mp:
        mp.setenv("DEV_ENV_STATE_DIR", str(state_dir))

        def mock_stop_plumbing_command(self, command, args):
          return {"status": "success", "message": "Environment stopped"}

        mp.setattr(StopCommand, "_run_plumbing_command", mock_stop_plumbing_command)

        stop_command.execute(stop_args)

    finally:
      os.chdir(original_cwd)

  def test_context_based_command_integration(self, tmp_path):
    """Test context-based command integration without Docker dependency"""
    from dev_env.commands.plumbing.context_create import ContextCreateCommand
    from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
    from dev_env.commands.plumbing.context_list import ContextListCommand
    from argparse import Namespace
    import io
    import sys

    # Setup test directory
    test_dir = tmp_path / "test-context"
    test_dir.mkdir()

    # Create context
    context_create = ContextCreateCommand()
    create_args = Namespace(name="integration-test", path=str(test_dir))

    # Capture JSON output from plumbing command
    captured_output = io.StringIO()
    with pytest.MonkeyPatch().context() as mp:
      mp.setattr(sys, "stdout", captured_output)
      context_create.run(create_args)

    # Verify context creation output
    output = captured_output.getvalue()
    assert output  # Should have JSON output

    # Test context resolution
    context_resolve = ContextResolveCommand()
    resolve_args = Namespace(name="integration-test")

    captured_output = io.StringIO()
    with pytest.MonkeyPatch().context() as mp:
      mp.setattr(sys, "stdout", captured_output)
      context_resolve.run(resolve_args)

    # Verify resolution output
    output = captured_output.getvalue()
    assert "integration-test" in output

    # Test context listing
    context_list = ContextListCommand()
    list_args = Namespace()

    captured_output = io.StringIO()
    with pytest.MonkeyPatch().context() as mp:
      mp.setattr(sys, "stdout", captured_output)
      context_list.run(list_args)

    # Verify listing output
    output = captured_output.getvalue()
    assert "integration-test" in output
