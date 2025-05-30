# tests/test_docker_comprehensive.py

import json
from unittest.mock import Mock, patch
import pytest
from dev_env.docker import DockerClient


class TestDockerClientCore:
  """Test core Docker client functionality with proper mocking"""

  @pytest.fixture
  def mock_connection(self):
    """Create a properly mocked HTTP connection"""
    with patch("dev_env.docker.UnixHTTPConnection") as mock_conn_class:
      mock_conn = Mock()
      mock_conn_class.return_value = mock_conn

      # Setup response mock
      mock_response = Mock()
      mock_response.status = 200
      mock_response.read.return_value = b'{"status": "ok"}'
      mock_conn.getresponse.return_value = mock_response

      yield mock_conn

  def test_request_success(self, mock_connection):
    """Test successful API request"""
    client = DockerClient()
    result = client._request("GET", "/info")

    assert result == {"status": "ok"}
    mock_connection.request.assert_called_once()

  def test_request_error_handling(self, mock_connection):
    """Test API error handling"""
    # Setup error response
    mock_response = Mock()
    mock_response.status = 404
    mock_response.read.return_value = b'{"message": "Not found"}'
    mock_connection.getresponse.return_value = mock_response

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: Not found"):
      client._request("GET", "/missing")

  def test_create_container_minimal(self, mock_connection):
    """Test container creation with minimal config"""
    mock_connection.getresponse().read.return_value = b'{"Id": "abc123"}'

    client = DockerClient()
    container_id = client.create_container(name="test", image="python:3.13")

    assert container_id == "abc123"

    # Verify request payload
    call_args = mock_connection.request.call_args
    body = json.loads(call_args[0][2])
    assert body["Image"] == "python:3.13"
    assert body["Hostname"] == "test"

  def test_create_container_with_security(self, mock_connection):
    """Test container creation with security config"""
    mock_connection.getresponse().read.return_value = b'{"Id": "abc123"}'

    # Mock environment config
    mock_env = Mock()
    mock_env.user = "1000:1000"
    mock_env.no_new_privileges = True
    mock_env.read_only_root_fs = False
    mock_env.drop_capabilities = ["ALL"]
    mock_env.add_capabilities = ["NET_ADMIN"]
    mock_env.to_docker_host_config.return_value = {"Memory": 2147483648, "CpuQuota": 200000}

    client = DockerClient()
    client.create_container(name="secure-test", image="python:3.13", env_config=mock_env)

    # Verify security settings applied
    call_args = mock_connection.request.call_args
    body = json.loads(call_args[0][2])
    assert body["User"] == "1000:1000"
    assert "no-new-privileges:true" in body["SecurityOpt"]
    assert body["HostConfig"]["CapDrop"] == ["ALL"]
    assert body["HostConfig"]["CapAdd"] == ["NET_ADMIN"]


class TestDockerImageOperations:
  """Test Docker image operations including streaming"""

  def test_pull_image_already_exists(self):
    """Test pull when image already exists locally"""
    with patch("dev_env.docker.UnixHTTPConnection") as mock_conn_class:
      mock_conn = Mock()
      mock_conn_class.return_value = mock_conn

      # First request checks if image exists - succeeds
      mock_response1 = Mock()
      mock_response1.status = 200
      mock_response1.read.return_value = b'{"id": "existing"}'

      mock_conn.getresponse.return_value = mock_response1

      client = DockerClient()
      progress_calls = []

      def progress(status, percent):
        progress_calls.append((status, percent))

      client.pull_image("python:3.13", progress)

      assert progress_calls == [("Image already exists", 100.0)]

  def test_pull_image_streaming(self):
    """Test image pull with streaming progress"""
    with patch("dev_env.docker.UnixHTTPConnection") as mock_conn_class:
      mock_conn = Mock()
      mock_conn_class.return_value = mock_conn

      # Mock image exists check (should fail)
      check_response = Mock()
      check_response.status = 404
      check_response.read.return_value = b'{"message": "No such image"}'

      # Mock streaming response for successful pull
      pull_response = Mock()
      pull_response.status = 200
      pull_response.readline.side_effect = [
        b'{"status": "Pulling", "id": "layer1"}\n',
        b'{"status": "Downloading", "id": "layer1", "progressDetail": {"current": 1024, "total": 2048}}\n',
        b'{"status": "Downloading", "id": "layer1", "progressDetail": {"current": 2048, "total": 2048}}\n',
        b'{"status": "Pull complete", "id": "layer1"}\n',
        b"",  # End of stream
      ]

      mock_conn.getresponse.side_effect = [check_response, pull_response]

      client = DockerClient()
      progress_calls = []

      def progress(status, percent):
        progress_calls.append((status, percent))

      client.pull_image("python:3.13", progress)

      # Verify progress was tracked
      assert any(p[1] == 50.0 for p in progress_calls)  # 1024/2048
      assert any(p[1] == 100.0 for p in progress_calls)  # Complete

  def test_parse_image_spec(self):
    """Test image specification parsing"""
    client = DockerClient()

    # Simple image
    registry, name, tag = client._parse_image_spec("ubuntu")
    assert registry == "docker.io"
    assert name == "library/ubuntu"
    assert tag == "latest"

    # Image with tag
    registry, name, tag = client._parse_image_spec("python:3.13")
    assert tag == "3.13"

    # Custom registry
    registry, name, tag = client._parse_image_spec("gcr.io/project/image:v1")
    assert registry == "gcr.io"
    assert name == "project/image"
    assert tag == "v1"


class TestDockerExecOperations:
  """Test container exec functionality"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_exec_run_success(self, mock_conn_class):
    """Test successful command execution"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock exec creation response
    create_response = Mock()
    create_response.status = 200
    create_response.read.return_value = b'{"Id": "exec123"}'

    # Mock exec start response
    start_response = Mock()
    start_response.status = 200
    start_response.read.return_value = b"Hello from container"

    # Mock exec inspect response
    inspect_response = Mock()
    inspect_response.status = 200
    inspect_response.read.return_value = b'{"ExitCode": 0}'

    mock_conn.getresponse.side_effect = [create_response, start_response, inspect_response]

    client = DockerClient()
    output, exit_code = client.exec_run("container123", ["echo", "hello"], user="root")

    assert output == b"Hello from container"
    assert exit_code == 0

    # Verify API calls
    assert mock_conn.request.call_count == 3


class TestDockerVolumeOperations:
  """Test volume management"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_volume(self, mock_conn_class):
    """Test volume creation"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"Name": "test-vol", "Driver": "local"}'
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.create_volume("test-vol", labels={"app": "dev-env"})

    assert result["Name"] == "test-vol"

    # Verify request
    call_args = mock_conn.request.call_args
    body = json.loads(call_args[0][2])
    assert body["Name"] == "test-vol"
    assert body["Labels"]["app"] == "dev-env"


class TestDockerContainerLifecycle:
  """Test complete container lifecycle"""

  @pytest.fixture
  def mock_docker(self):
    """Setup mocked Docker client"""
    with patch("dev_env.docker.UnixHTTPConnection") as mock_conn_class:
      mock_conn = Mock()
      mock_conn_class.return_value = mock_conn

      # Default successful response
      mock_response = Mock()
      mock_response.status = 200
      mock_response.read.return_value = b'{"status": "ok"}'
      mock_conn.getresponse.return_value = mock_response

      yield mock_conn

  def test_container_lifecycle(self, mock_docker):
    """Test create, start, stop, remove container flow"""
    client = DockerClient()

    # Create
    mock_docker.getresponse().read.return_value = b'{"Id": "abc123"}'
    container_id = client.create_container("test", "python:3.13")
    assert container_id == "abc123"

    # Start
    client.start_container(container_id)
    assert "/containers/abc123/start" in str(mock_docker.request.call_args_list)

    # Stop
    client.stop_container(container_id, timeout=5)
    assert any("stop" in str(call) for call in mock_docker.request.call_args_list)

    # Remove
    client.remove_container(container_id)
    assert any("DELETE" in str(call) for call in mock_docker.request.call_args_list)
