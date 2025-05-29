"""Tests for Docker API client operations"""

import json
import pytest
from unittest.mock import Mock, patch

from dev_env.docker import DockerClient


class TestDockerClient:
  """Test DockerClient initialization and basic operations"""

  def test_init_default_socket(self):
    """Test DockerClient initialization with default socket path"""
    client = DockerClient()
    assert client.socket_path == "/var/run/docker.sock"

  def test_init_custom_socket(self):
    """Test DockerClient initialization with custom socket path"""
    custom_path = "/custom/docker.sock"
    client = DockerClient(socket_path=custom_path)
    assert client.socket_path == custom_path


class TestDockerAPIRequests:
  """Test Docker API request formatting and execution"""

  @patch("http.client.HTTPConnection")
  def test_request_get(self, mock_http_connection):
    """Test GET request formatting"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"test": "data"}'
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client._request("GET", "/containers/json")

    # Verify request was made correctly
    mock_conn.request.assert_called_once_with(
      "GET", "/containers/json", body=None, headers={"Content-Type": "application/json"}
    )
    assert result == {"test": "data"}

  @patch("http.client.HTTPConnection")
  def test_request_post_with_data(self, mock_http_connection):
    """Test POST request with JSON data"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = b'{"Id": "container123"}'
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    data = {"Image": "python:3.13", "Cmd": ["sleep", "infinity"]}
    result = client._request("POST", "/containers/create", data=data)

    # Verify request was made with proper JSON encoding
    expected_body = json.dumps(data).encode("utf-8")
    mock_conn.request.assert_called_once_with(
      "POST", "/containers/create", body=expected_body, headers={"Content-Type": "application/json"}
    )
    assert result == {"Id": "container123"}

  @patch("http.client.HTTPConnection")
  def test_request_error_handling(self, mock_http_connection):
    """Test API request error handling"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 404
    mock_response.read.return_value = b'{"message": "No such container"}'
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()

    with pytest.raises(RuntimeError, match="Docker API error"):
      client._request("GET", "/containers/nonexistent/json")

  @patch("http.client.HTTPConnection")
  def test_request_connection_error(self, mock_http_connection):
    """Test handling of connection errors"""
    mock_http_connection.side_effect = ConnectionError("Cannot connect to Docker daemon")

    client = DockerClient()

    with pytest.raises(RuntimeError, match="Failed to connect to Docker"):
      client._request("GET", "/containers/json")


class TestContainerOperations:
  """Test container-related API operations"""

  @patch("http.client.HTTPConnection")
  def test_create_container_minimal(self, mock_http_connection):
    """Test creating container with minimal parameters"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = b'{"Id": "container123"}'
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    container_id = client.create_container(name="test-container", image="python:3.13")

    # Verify request format
    call_args = mock_conn.request.call_args
    assert call_args[0] == ("POST", "/containers/create?name=test-container")

    # Parse the request body
    body_data = json.loads(call_args[1]["body"])
    assert body_data["Image"] == "python:3.13"
    assert "HostConfig" in body_data
    assert container_id == "container123"

  @patch("http.client.HTTPConnection")
  def test_create_container_full_config(self, mock_http_connection):
    """Test creating container with full configuration"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = b'{"Id": "container456"}'
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    container_id = client.create_container(
      name="full-container",
      image="ubuntu:22.04",
      command=["bash", "-c", "sleep infinity"],
      environment={"ENV_VAR": "value", "DEBUG": "true"},
      volumes={"/host/path": {"bind": "/container/path", "mode": "rw"}},
      ports={22: {"HostPort": "2222"}, 80: {"HostPort": "8080"}},
      network="custom-network",
    )

    # Verify full configuration was properly formatted
    call_args = mock_conn.request.call_args
    body_data = json.loads(call_args[1]["body"])

    assert body_data["Image"] == "ubuntu:22.04"
    assert body_data["Cmd"] == ["bash", "-c", "sleep infinity"]
    assert body_data["Env"] == ["ENV_VAR=value", "DEBUG=true"]
    assert body_data["HostConfig"]["Binds"] == ["/host/path:/container/path:rw"]
    assert body_data["HostConfig"]["PortBindings"] == {
      "22/tcp": [{"HostPort": "2222"}],
      "80/tcp": [{"HostPort": "8080"}],
    }
    assert body_data["NetworkingConfig"]["EndpointsConfig"]["custom-network"] == {}
    assert container_id == "container456"

  @patch("http.client.HTTPConnection")
  def test_start_container(self, mock_http_connection):
    """Test starting a container"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 204  # No content for start
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    client.start_container("container123")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "POST", "/containers/container123/start", body=None, headers={"Content-Type": "application/json"}
    )

  @patch("http.client.HTTPConnection")
  def test_stop_container(self, mock_http_connection):
    """Test stopping a container"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    client.stop_container("container123")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "POST", "/containers/container123/stop", body=None, headers={"Content-Type": "application/json"}
    )

  @patch("http.client.HTTPConnection")
  def test_remove_container(self, mock_http_connection):
    """Test removing a container"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    client.remove_container("container123")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "DELETE", "/containers/container123", body=None, headers={"Content-Type": "application/json"}
    )

  @patch("http.client.HTTPConnection")
  def test_get_container(self, mock_http_connection):
    """Test getting container information"""
    container_data = {
      "Id": "container123",
      "State": {"Status": "running", "Running": True},
      "Config": {"Image": "python:3.13"},
      "NetworkSettings": {"Ports": {"22/tcp": [{"HostPort": "2222"}]}},
    }

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(container_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.get_container("container123")

    # Verify request and response
    mock_conn.request.assert_called_once_with(
      "GET", "/containers/container123/json", body=None, headers={"Content-Type": "application/json"}
    )
    assert result == container_data


class TestVolumeOperations:
  """Test volume-related API operations"""

  @patch("http.client.HTTPConnection")
  def test_create_volume(self, mock_http_connection):
    """Test creating a volume"""
    volume_data = {"Name": "test-volume", "Driver": "local", "Mountpoint": "/var/lib/docker/volumes/test-volume/_data"}

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(volume_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.create_volume("test-volume", labels={"env": "test"})

    # Verify request
    call_args = mock_conn.request.call_args
    assert call_args[0] == ("POST", "/volumes/create")

    body_data = json.loads(call_args[1]["body"])
    assert body_data["Name"] == "test-volume"
    assert body_data["Labels"] == {"env": "test"}
    assert result == volume_data

  @patch("http.client.HTTPConnection")
  def test_remove_volume(self, mock_http_connection):
    """Test removing a volume"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    client.remove_volume("test-volume")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "DELETE", "/volumes/test-volume", body=None, headers={"Content-Type": "application/json"}
    )

  @patch("http.client.HTTPConnection")
  def test_get_volume_usage(self, mock_http_connection):
    """Test getting volume usage information"""
    system_df_data = {
      "Volumes": [
        {"Name": "test-volume", "UsageData": {"Size": 1048576, "RefCount": 1}},
        {"Name": "other-volume", "UsageData": {"Size": 2097152, "RefCount": 2}},
      ]
    }

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(system_df_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.get_volume_usage("test-volume")

    # Verify request and response parsing
    mock_conn.request.assert_called_once_with(
      "GET", "/system/df", body=None, headers={"Content-Type": "application/json"}
    )
    assert result["size"] == 1048576
    assert result["ref_count"] == 1


class TestNetworkOperations:
  """Test network-related API operations"""

  @patch("http.client.HTTPConnection")
  def test_create_network(self, mock_http_connection):
    """Test creating a network"""
    network_data = {"Id": "network123", "Warning": ""}

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(network_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.create_network(
      name="test-network", driver="bridge", options={"subnet": "172.20.0.0/16"}, labels={"env": "test"}
    )

    # Verify request
    call_args = mock_conn.request.call_args
    assert call_args[0] == ("POST", "/networks/create")

    body_data = json.loads(call_args[1]["body"])
    assert body_data["Name"] == "test-network"
    assert body_data["Driver"] == "bridge"
    assert body_data["Options"] == {"subnet": "172.20.0.0/16"}
    assert body_data["Labels"] == {"env": "test"}
    assert result == network_data

  @patch("http.client.HTTPConnection")
  def test_get_network(self, mock_http_connection):
    """Test getting network information"""
    network_data = {"Name": "test-network", "Id": "network123", "Driver": "bridge", "Containers": {}}

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(network_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.get_network("test-network")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "GET", "/networks/test-network", body=None, headers={"Content-Type": "application/json"}
    )
    assert result == network_data

  @patch("http.client.HTTPConnection")
  def test_remove_network(self, mock_http_connection):
    """Test removing a network"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 204
    mock_response.read.return_value = b""
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    client.remove_network("test-network")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "DELETE", "/networks/test-network", body=None, headers={"Content-Type": "application/json"}
    )


class TestExecOperations:
  """Test exec-related API operations"""

  @patch("http.client.HTTPConnection")
  def test_create_exec(self, mock_http_connection):
    """Test creating exec instance"""
    exec_data = {"Id": "exec123"}

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps(exec_data).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    exec_id = client.create_exec(
      container_id="container123", cmd=["ls", "-la"], user="root", tty=True, attach_stdout=True, attach_stderr=True
    )

    # Verify request
    call_args = mock_conn.request.call_args
    assert call_args[0] == ("POST", "/containers/container123/exec")

    body_data = json.loads(call_args[1]["body"])
    assert body_data["Cmd"] == ["ls", "-la"]
    assert body_data["User"] == "root"
    assert body_data["Tty"] is True
    assert body_data["AttachStdout"] is True
    assert body_data["AttachStderr"] is True
    assert exec_id == "exec123"

  @patch("http.client.HTTPConnection")
  def test_start_exec(self, mock_http_connection):
    """Test starting exec instance"""
    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = b"command output"
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    output = client.start_exec("exec123")

    # Verify request
    call_args = mock_conn.request.call_args
    assert call_args[0] == ("POST", "/exec/exec123/start")

    body_data = json.loads(call_args[1]["body"])
    assert body_data["Detach"] is False
    assert body_data["Tty"] is False
    assert output == b"command output"

  @patch("http.client.HTTPConnection")
  def test_get_exec_info(self, mock_http_connection):
    """Test getting exec instance information"""
    exec_info = {
      "ID": "exec123",
      "Running": False,
      "ExitCode": 0,
      "ProcessConfig": {"entrypoint": "ls", "arguments": ["-la"]},
    }

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(exec_info).encode()
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    result = client.get_exec_info("exec123")

    # Verify request
    mock_conn.request.assert_called_once_with(
      "GET", "/exec/exec123/json", body=None, headers={"Content-Type": "application/json"}
    )
    assert result == exec_info


class TestImageOperations:
  """Test image-related API operations"""

  @patch("http.client.HTTPConnection")
  def test_pull_image_success(self, mock_http_connection):
    """Test successful image pull with progress callback"""
    progress_responses = [
      b'{"status":"Pulling from library/python","id":"3.13"}\n',
      b'{"status":"Downloading","progressDetail":{"current":1024,"total":2048},"progress":"[========================>  ] 1024B/2048B","id":"layer1"}\n',
      b'{"status":"Download complete","id":"layer1"}\n',
      b'{"status":"Pull complete","id":"3.13"}\n',
    ]

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.side_effect = progress_responses
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    progress_calls = []

    def progress_callback(status, progress):
      progress_calls.append((status, progress))

    client = DockerClient()
    client.pull_image("python:3.13", progress_callback)

    # Verify request
    mock_conn.request.assert_called_once_with(
      "POST", "/images/create?fromImage=python%3A3.13", body=None, headers={"Content-Type": "application/json"}
    )

    # Verify progress callback was called
    assert len(progress_calls) > 0
    assert any("Downloading" in call[0] for call in progress_calls)

  @patch("http.client.HTTPConnection")
  def test_wait_for_container_ready(self, mock_http_connection):
    """Test waiting for container to be ready"""
    # First call returns "starting", second call returns "running"
    responses = [
      json.dumps({"State": {"Status": "starting", "Running": False}}).encode(),
      json.dumps({"State": {"Status": "running", "Running": True}}).encode(),
    ]

    mock_conn = Mock()
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.side_effect = responses
    mock_conn.getresponse.return_value = mock_response
    mock_http_connection.return_value = mock_conn

    client = DockerClient()
    with patch("time.sleep"):  # Mock sleep to speed up test
      result = client.wait_for_container_ready("container123", timeout=10)

    assert result is True
    # Should have made 2 requests (first starting, second running)
    assert mock_conn.request.call_count == 2
