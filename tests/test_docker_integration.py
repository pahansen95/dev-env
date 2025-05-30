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


# tests/test_e2e_workflow.py


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.skipif(not check_docker_available(), reason="Docker not available")
class TestEndToEndWorkflow:
  """Complete end-to-end workflow tests"""

  @pytest.fixture
  def test_config_file(self, tmp_path):
    """Create test configuration file"""
    config_file = tmp_path / "test_env.py"
    config_file.write_text("""
from dev_env.config import Environment, VolumeMount

config = Environment(
    name="e2e-test",
    base_image="python:3.13-alpine",
    command=["sleep", "infinity"],
    volumes=[
        VolumeMount(source="test-data", target="/data")
    ],
    ports={8080: {"HostPort": 18080}},
    environment={"TEST_VAR": "test_value"}
)
""")
    return config_file

  def test_complete_environment_lifecycle(self, test_config_file, tmp_path):
    """Test complete workflow from config to teardown"""
    from dev_env.cli import cmd_up, cmd_exec, cmd_down
    from argparse import Namespace

    # Setup args
    state_dir = tmp_path / "state"

    # Create environment
    up_args = Namespace(config=test_config_file, name="e2e-test", state_dir=state_dir)

    result = cmd_up(up_args)
    assert result == 0

    # Execute command in environment
    exec_args = Namespace(name="e2e-test", command=["echo", "$TEST_VAR"], state_dir=state_dir)

    # Capture output
    import io
    import sys

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured

    try:
      result = cmd_exec(exec_args)
      output = captured.getvalue()
      assert result == 0
      assert "test_value" in output
    finally:
      sys.stdout = old_stdout

    # Teardown environment
    down_args = Namespace(name="e2e-test", volumes=True, state_dir=state_dir)

    result = cmd_down(down_args)
    assert result == 0
