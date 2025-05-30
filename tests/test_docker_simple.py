"""Simple Docker tests focusing on key operations"""

import json
import pytest
from unittest.mock import Mock, patch

from dev_env.docker import DockerClient


class TestDockerClientBasics:
  """Test basic Docker client operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_docker_client_init(self, mock_conn_class):
    """Test DockerClient initialization"""
    client = DockerClient()
    assert client.socket_path == "/var/run/docker.sock"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_ping_success(self, mock_conn_class):
    """Test successful Docker ping"""
    # Setup mock connection
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock successful response
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'"OK"'
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.ping()

    assert result is True

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_ping_failure(self, mock_conn_class):
    """Test Docker ping failure"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock error response
    mock_response = Mock()
    mock_response.status = 500
    mock_response.read.return_value = b'{"message": "Server Error"}'
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.ping()

    assert result is False

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_ping_connection_error(self, mock_conn_class):
    """Test Docker ping with connection error"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn
    mock_conn.request.side_effect = Exception("Connection failed")

    client = DockerClient()
    result = client.ping()

    assert result is False


class TestContainerOperations:
  """Test container operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_list_containers(self, mock_conn_class):
    """Test listing containers"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock container list response
    containers = [
      {"Id": "cont1", "Names": ["/container1"], "State": "running"},
      {"Id": "cont2", "Names": ["/container2"], "State": "running"},
    ]
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(containers).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.list_containers()

    assert len(result) == 2
    assert result[0]["Id"] == "cont1"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_get_container(self, mock_conn_class):
    """Test getting container info"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    container_info = {"Id": "test123", "Names": ["/test-container"], "State": "running"}
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(container_info).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.get_container("test123")

    assert result["Id"] == "test123"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_start_container(self, mock_conn_class):
    """Test starting a container"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 204  # No content for successful start
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    # Should not raise exception
    client.start_container("test123")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_stop_container(self, mock_conn_class):
    """Test stopping a container"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.stop_container("test123")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_remove_container(self, mock_conn_class):
    """Test removing a container"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.remove_container("test123")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_basic(self, mock_conn_class):
    """Test creating a basic container"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_123", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    container_id = client.create_container(name="test-container", image="python:3.13")

    assert container_id == "new_container_123"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_with_command_and_env(self, mock_conn_class):
    """Test creating container with command and environment variables"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_456", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    container_id = client.create_container(
      name="test-with-cmd",
      image="python:3.13",
      command=["python", "-c", "print('hello')"],
      environment={"TEST_VAR": "test_value", "NODE_ENV": "production"},
    )

    assert container_id == "new_container_456"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_with_volumes(self, mock_conn_class):
    """Test creating container with volume mounts"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_789", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    volumes = {
      "/host/data": {"bind": "/container/data", "mode": "rw"},
      "/host/config": {"bind": "/container/config", "mode": "ro"},
    }
    container_id = client.create_container(name="test-with-volumes", image="python:3.13", volumes=volumes)

    assert container_id == "new_container_789"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_with_ports(self, mock_conn_class):
    """Test creating container with port mappings"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_ports", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    ports = {"8080": {"HostIp": "0.0.0.0", "HostPort": "8080"}, "3000": {"HostIp": "", "HostPort": "3000"}}
    container_id = client.create_container(name="test-with-ports", image="python:3.13", ports=ports)

    assert container_id == "new_container_ports"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_with_network(self, mock_conn_class):
    """Test creating container with custom network"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_net", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    container_id = client.create_container(name="test-with-network", image="python:3.13", network="custom-network")

    assert container_id == "new_container_net"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_with_env_config(self, mock_conn_class):
    """Test creating container with environment configuration"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    create_response = {"Id": "new_container_secure", "Warnings": []}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(create_response).encode()
    mock_conn.getresponse.return_value = mock_response

    # Mock environment config
    mock_env_config = Mock()
    mock_env_config.user = "1000:1000"
    mock_env_config.no_new_privileges = True
    mock_env_config.read_only_root_fs = True
    mock_env_config.drop_capabilities = ["NET_RAW", "SYS_ADMIN"]
    mock_env_config.add_capabilities = ["SYS_TIME"]
    mock_env_config.to_docker_host_config.return_value = {"Memory": 512 * 1024 * 1024}

    client = DockerClient()
    container_id = client.create_container(name="test-secure", image="python:3.13", env_config=mock_env_config)

    assert container_id == "new_container_secure"


class TestImageOperations:
  """Test image operations"""

  def test_parse_image_spec(self):
    """Test image specification parsing"""
    client = DockerClient()

    # Test different image formats
    registry, name, tag = client._parse_image_spec("python")
    assert name == "library/python"
    assert tag == "latest"
    assert registry == "docker.io"

    registry, name, tag = client._parse_image_spec("python:3.13")
    assert name == "library/python"
    assert tag == "3.13"
    assert registry == "docker.io"

    registry, name, tag = client._parse_image_spec("myregistry.com/python:3.13")
    assert name == "python"
    assert tag == "3.13"
    assert registry == "myregistry.com"

  def test_parse_image_spec_additional_cases(self):
    """Test additional image specification parsing cases"""
    client = DockerClient()

    # Test localhost registry
    registry, name, tag = client._parse_image_spec("localhost:5000/myapp:dev")
    assert name == "myapp"
    assert tag == "dev"
    assert registry == "localhost:5000"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_success(self, mock_conn_class):
    """Test successful image pull"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should fail)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Mock pull response
    pull_response = Mock()
    pull_response.status = 200
    pull_response.readline.side_effect = [
      b'{"status":"Pulling from library/python","id":"3.13"}\n',
      b'{"status":"Pull complete","id":"3.13"}\n',
      b"",  # End of stream
    ]

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    # Should not raise an exception
    client.pull_image("python:3.13")

    # Verify two requests were made (check + pull)
    assert mock_conn.request.call_count == 2

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_already_exists(self, mock_conn_class):
    """Test pulling image that already exists"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should succeed)
    check_response = Mock()
    check_response.status = 200
    check_response.read.return_value = b'{"Id": "sha256:abc123"}'
    mock_conn.getresponse.return_value = check_response

    progress_callback = Mock()

    client = DockerClient()
    client.pull_image("python:3.13", progress_callback)

    # Verify progress callback was called to indicate image exists
    progress_callback.assert_called_with("Image already exists", 100.0)


class TestVolumeOperations:
  """Test volume operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_volume(self, mock_conn_class):
    """Test creating a volume"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    volume_info = {"Name": "test-volume", "Driver": "local", "Mountpoint": "/var/lib/docker/volumes/test-volume/_data"}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(volume_info).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.create_volume("test-volume")

    assert result["Name"] == "test-volume"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_remove_volume(self, mock_conn_class):
    """Test removing a volume"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.remove_volume("test-volume")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_list_volumes(self, mock_conn_class):
    """Test listing volumes"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    volumes_data = {"Volumes": [{"Name": "vol1", "Driver": "local"}, {"Name": "vol2", "Driver": "local"}]}
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(volumes_data).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.list_volumes()

    assert len(result) == 2
    assert result[0]["Name"] == "vol1"


class TestExecOperations:
  """Test container exec operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_exec_run_basic(self, mock_conn_class):
    """Test basic command execution"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock the sequence: create exec, start exec, inspect exec
    responses = [
      # Create exec response
      Mock(status=201, read=lambda: json.dumps({"Id": "exec123"}).encode()),
      # Start exec response
      Mock(status=200, read=lambda: b"Hello World\n"),
      # Inspect exec response
      Mock(status=200, read=lambda: json.dumps({"ExitCode": 0, "Running": False}).encode()),
    ]
    mock_conn.getresponse.side_effect = responses

    client = DockerClient()
    output, exit_code = client.exec_run("container123", ["echo", "Hello World"])

    assert output == b"Hello World\n"
    assert exit_code == 0


class TestLogsOperations:
  """Test container logs operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_get_container_logs(self, mock_conn_class):
    """Test getting container logs"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b"Log line 1\nLog line 2\n"
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    logs = client.get_container_logs("container123")

    assert logs == b"Log line 1\nLog line 2\n"


class TestNetworkOperations:
  """Test Docker network operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_network(self, mock_conn_class):
    """Test creating a Docker network"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    network_info = {"Id": "net123", "Name": "test-network", "Driver": "bridge"}
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(network_info).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    result = client.create_network("test-network", driver="bridge")

    assert result["Name"] == "test-network"

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_remove_network(self, mock_conn_class):
    """Test removing a Docker network"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.remove_network("test-network")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_connect_container_to_network(self, mock_conn_class):
    """Test connecting container to network"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.connect_container_to_network("test-network", "container123")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_disconnect_container_from_network(self, mock_conn_class):
    """Test disconnecting container from network"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    client.disconnect_container_from_network("test-network", "container123")


class TestContainerWaitOperations:
  """Test container wait operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  @patch("time.sleep")
  @patch("time.time")
  def test_wait_for_container_ready_success(self, mock_time, mock_sleep, mock_conn_class):
    """Test waiting for container to be ready"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock time progression
    mock_time.side_effect = [0, 5, 10]  # Start, first check, success

    # Mock container info response - running state
    container_info = {"State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00Z"}}

    # Mock exec response for readiness check
    exec_create_response = Mock()
    exec_create_response.status = 201
    exec_create_response.read.return_value = json.dumps({"Id": "exec123"}).encode()

    exec_start_response = Mock()
    exec_start_response.status = 200
    exec_start_response.read.return_value = b"ready\n"

    exec_inspect_response = Mock()
    exec_inspect_response.status = 200
    exec_inspect_response.read.return_value = json.dumps({"ExitCode": 0}).encode()

    container_response = Mock()
    container_response.status = 200
    container_response.read.return_value = json.dumps(container_info).encode()

    mock_conn.getresponse.side_effect = [
      container_response,
      exec_create_response,
      exec_start_response,
      exec_inspect_response,
    ]

    client = DockerClient()
    result = client.wait_for_container_ready("container123", timeout=30)

    assert result is True

  @patch("dev_env.docker.UnixHTTPConnection")
  @patch("time.sleep")
  @patch("time.time")
  def test_wait_for_container_ready_timeout(self, mock_time, mock_sleep, mock_conn_class):
    """Test waiting for container timeout"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock time progression - timeout after 30 seconds
    mock_time.side_effect = [0, 31]  # Start, timeout

    client = DockerClient()
    result = client.wait_for_container_ready("container123", timeout=30)

    assert result is False


class TestErrorHandling:
  """Test Docker error handling scenarios"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_container_not_found(self, mock_conn_class):
    """Test container not found error"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 404
    mock_response.read.return_value = json.dumps({"message": "No such container"}).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()

    with pytest.raises(Exception, match="Docker API error"):
      client.get_container("nonexistent")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_server_error(self, mock_conn_class):
    """Test Docker server error"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 500
    mock_response.read.return_value = json.dumps({"message": "Internal server error"}).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()

    with pytest.raises(Exception, match="Docker API error"):
      client.list_containers()

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_network_error(self, mock_conn_class):
    """Test network connection error"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn
    mock_conn.request.side_effect = ConnectionError("Network unreachable")

    client = DockerClient()

    # ping() should handle connection errors gracefully
    result = client.ping()
    assert result is False

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_error_response(self, mock_conn_class):
    """Test image pull with error response"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should fail)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Mock pull error response
    pull_response = Mock()
    pull_response.status = 404
    pull_response.read.return_value = b'{"message": "Repository not found"}'

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: Repository not found"):
      client.pull_image("nonexistent/image:latest")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_no_error_data(self, mock_conn_class):
    """Test image pull with HTTP error but no error data"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should fail)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Mock pull error response with no body
    pull_response = Mock()
    pull_response.status = 500
    pull_response.read.return_value = b""  # Empty response body

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: HTTP 500"):
      client.pull_image("broken/image:latest")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_stream_error(self, mock_conn_class):
    """Test image pull with streaming error"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should fail)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Mock pull response with error in stream
    pull_response = Mock()
    pull_response.status = 200
    pull_response.readline.side_effect = [
      b'{"status":"Pulling from library/python","id":"3.13"}\n',
      b'{"error":"Authentication required"}\n',
      b"",  # End of stream
    ]

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Pull failed: Authentication required"):
      client.pull_image("private/image:latest")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_invalid_json_in_stream(self, mock_conn_class):
    """Test image pull with invalid JSON in stream"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock image exists check (should fail)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Mock pull response with invalid JSON
    pull_response = Mock()
    pull_response.status = 200
    pull_response.readline.side_effect = [
      b'{"status":"Pulling from library/python"}\n',
      b"invalid json line\n",  # This should be skipped
      b'{"status":"Pull complete"}\n',
      b"",  # End of stream
    ]

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    # Should not raise an exception - invalid JSON should be skipped
    client.pull_image("python:3.13")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_exec_run_error_response(self, mock_conn_class):
    """Test exec run with error response"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock exec creation success
    exec_create_response = Mock()
    exec_create_response.status = 201
    exec_create_response.read.return_value = json.dumps({"Id": "exec123"}).encode()

    # Mock exec start error
    exec_start_response = Mock()
    exec_start_response.status = 404
    exec_start_response.read.return_value = json.dumps({"message": "No such exec instance"}).encode()

    mock_conn.getresponse.side_effect = [exec_create_response, exec_start_response]

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: No such exec instance"):
      client.exec_run("container123", ["echo", "test"])

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_exec_run_no_error_data(self, mock_conn_class):
    """Test exec run with HTTP error but no error data"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock exec creation success
    exec_create_response = Mock()
    exec_create_response.status = 201
    exec_create_response.read.return_value = json.dumps({"Id": "exec123"}).encode()

    # Mock exec start error with no body
    exec_start_response = Mock()
    exec_start_response.status = 500
    exec_start_response.read.return_value = b""

    mock_conn.getresponse.side_effect = [exec_create_response, exec_start_response]

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: HTTP 500"):
      client.exec_run("container123", ["echo", "test"])

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_get_container_logs_error(self, mock_conn_class):
    """Test container logs with error response"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 404
    mock_response.read.return_value = json.dumps({"message": "No such container"}).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: No such container"):
      client.get_container_logs("nonexistent")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_get_container_logs_no_error_data(self, mock_conn_class):
    """Test container logs with HTTP error but no error data"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 500
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    with pytest.raises(RuntimeError, match="Docker API error: HTTP 500"):
      client.get_container_logs("container123")

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_wait_for_container_ready_not_running(self, mock_conn_class):
    """Test waiting for container that is not running"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock container info response - not running
    container_info = {"State": {"Status": "exited", "StartedAt": "2024-01-01T00:00:00Z"}}
    container_response = Mock()
    container_response.status = 200
    container_response.read.return_value = json.dumps(container_info).encode()
    mock_conn.getresponse.return_value = container_response

    client = DockerClient()
    result = client.wait_for_container_ready("container123", timeout=5)

    assert result is False

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_wait_for_container_ready_exec_failure(self, mock_conn_class):
    """Test waiting for container with exec command failure"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Mock container info response - running state
    container_info = {"State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00Z"}}
    container_response = Mock()
    container_response.status = 200
    container_response.read.return_value = json.dumps(container_info).encode()

    # Mock exec failure
    mock_conn.getresponse.side_effect = [container_response, Exception("Exec failed")]

    client = DockerClient()

    # Should handle exec failure gracefully and continue trying
    with patch("time.sleep"):
      with patch("time.time", side_effect=[0, 5, 31]):  # timeout after retries
        result = client.wait_for_container_ready("container123", timeout=30)

    assert result is False
