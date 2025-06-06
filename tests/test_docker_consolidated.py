"""Consolidated Docker client tests - combining simple and comprehensive tests"""

import json
import pytest
from unittest.mock import Mock, patch

from dev_env.docker import DockerClient


class TestDockerClientCore:
  """Core Docker client functionality tests"""

  @pytest.mark.parametrize(
    "method,args,request_path,http_method",
    [
      ("ping", [], "/_ping", "GET"),
      ("list_containers", [], "/containers/json?all=False", "GET"),  # Fixed: all=False is the default
      ("get_container", ["test123"], "/containers/test123/json", "GET"),
      ("start_container", ["test123"], "/containers/test123/start", "POST"),
      ("stop_container", ["test123"], "/containers/test123/stop?t=10", "POST"),
      ("remove_container", ["test123"], "/containers/test123", "DELETE"),
    ],
  )
  @patch("dev_env.docker.UnixHTTPConnection")
  def test_docker_api_requests(self, mock_conn_class, method, args, request_path, http_method):
    """Test that Docker methods make correct API requests"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Setup appropriate response based on method
    mock_response = Mock()
    if method == "ping":
      mock_response.status = 200
      mock_response.read.return_value = b'"OK"'
    elif method in ["start_container", "stop_container", "remove_container"]:
      mock_response.status = 204
      mock_response.read.return_value = b""
    else:
      mock_response.status = 200
      mock_response.read.return_value = json.dumps([{"Id": "test"}]).encode()

    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    getattr(client, method)(*args)

    # Verify the request was made correctly
    mock_conn.request.assert_called()
    call_args = mock_conn.request.call_args
    assert call_args[0][0] == http_method
    assert request_path in call_args[0][1]


class TestDockerOperationResults:
  """Test Docker operations return expected results"""

  @pytest.mark.parametrize(
    "operation,expected_result",
    [
      ("list_containers", [{"Id": "c1", "Names": ["/container1"]}, {"Id": "c2", "Names": ["/container2"]}]),
      ("get_container", {"Id": "test123", "State": {"Status": "running"}}),
      ("create_volume", {"Name": "test-volume", "Driver": "local"}),
      ("list_volumes", [{"Name": "vol1"}, {"Name": "vol2"}]),
    ],
  )
  @patch("dev_env.docker.UnixHTTPConnection")
  def test_operation_results(self, mock_conn_class, operation, expected_result):
    """Test operations return properly formatted results"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 200 if operation != "create_volume" else 201

    # Handle list_volumes special case
    if operation == "list_volumes":
      mock_response.read.return_value = json.dumps({"Volumes": expected_result}).encode()
    else:
      mock_response.read.return_value = json.dumps(expected_result).encode()

    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()

    # Call the appropriate method
    if operation == "list_containers":
      result = client.list_containers()
    elif operation == "get_container":
      result = client.get_container("test123")
    elif operation == "create_volume":
      result = client.create_volume("test-volume")
    elif operation == "list_volumes":
      result = client.list_volumes()

    assert result == expected_result


class TestDockerErrorHandling:
  """Consolidated Docker error handling tests"""

  @pytest.mark.parametrize(
    "status,error_body,expected_error",
    [
      (404, {"message": "No such container"}, "No such container"),
      (500, {"message": "Internal server error"}, "Internal server error"),
      (403, {"message": "Permission denied"}, "Permission denied"),
      (500, None, "HTTP 500"),  # No error body
    ],
  )
  @patch("dev_env.docker.UnixHTTPConnection")
  def test_api_error_responses(self, mock_conn_class, status, error_body, expected_error):
    """Test consistent error handling across all API errors"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = status

    if error_body:
      mock_response.read.return_value = json.dumps(error_body).encode()
    else:
      mock_response.read.return_value = b""

    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()

    # All non-success responses should raise exceptions
    with pytest.raises((RuntimeError, Exception)) as exc_info:
      client.get_container("test123")

    assert expected_error in str(exc_info.value)

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_connection_error_handling(self, mock_conn_class):
    """Test handling of connection errors"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn
    mock_conn.request.side_effect = ConnectionError("Network unreachable")

    client = DockerClient()

    # ping() should handle connection errors gracefully
    assert client.ping() is False

    # Other methods should raise
    with pytest.raises(ConnectionError):
      client.list_containers()


class TestDockerContainerCreation:
  """Test container creation with various configurations"""

  @pytest.mark.parametrize(
    "config",
    [
      {"name": "basic", "image": "python:3.13"},
      {"name": "with-cmd", "image": "python:3.13", "command": ["python", "-c", "print('hello')"]},
      {"name": "with-env", "image": "python:3.13", "environment": {"VAR1": "val1", "VAR2": "val2"}},
      {"name": "with-volumes", "image": "python:3.13", "volumes": {"/host": {"bind": "/container", "mode": "rw"}}},
      {"name": "with-ports", "image": "python:3.13", "ports": {"80": {"HostPort": "8080"}}},
      {"name": "with-network", "image": "python:3.13", "network": "custom-net"},
    ],
  )
  @patch("dev_env.docker.UnixHTTPConnection")
  def test_create_container_configurations(self, mock_conn_class, config):
    """Test container creation with different configurations"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 201
    mock_response.read.return_value = json.dumps({"Id": f"container_{config['name']}"}).encode()
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    container_id = client.create_container(**config)

    assert container_id == f"container_{config['name']}"

    # Verify request was made
    mock_conn.request.assert_called()
    call_args = mock_conn.request.call_args

    # Verify configuration was included in request body
    if len(call_args[0]) > 2 and call_args[0][2]:
      body = json.loads(call_args[0][2])
      assert body["Image"] == config["image"]
      if "command" in config:
        assert body["Cmd"] == config["command"]


class TestDockerImageOperations:
  """Test Docker image-related operations"""

  @pytest.mark.parametrize(
    "image_spec,expected_parse",
    [
      ("python", ("docker.io", "library/python", "latest")),
      ("python:3.13", ("docker.io", "library/python", "3.13")),
      ("myregistry.com/app:v1", ("myregistry.com", "app", "v1")),
      ("localhost:5000/test:dev", ("localhost:5000", "test", "dev")),
      ("user/repo", ("docker.io", "user/repo", "latest")),
    ],
  )
  def test_image_spec_parsing(self, image_spec, expected_parse):
    """Test parsing of various image specification formats"""
    client = DockerClient()
    result = client._parse_image_spec(image_spec)
    assert result == expected_parse

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_pull_image_flow(self, mock_conn_class):
    """Test complete image pull flow - FIXED readline mock"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Create readline responses as a list
    readline_responses = [
      b'{"status":"Pulling from library/python","id":"3.13"}\n',
      b'{"status":"Download complete","id":"layer1"}\n',
      b'{"status":"Pull complete"}\n',
      b"",  # Empty line signals end
    ]

    # First request checks if image exists (404)
    check_response = Mock()
    check_response.status = 404
    check_response.read.return_value = b'{"message": "No such image"}'

    # Second request pulls the image
    pull_response = Mock()
    pull_response.status = 200
    # Create a side_effect that returns lines sequentially
    pull_response.readline.side_effect = readline_responses

    mock_conn.getresponse.side_effect = [check_response, pull_response]

    client = DockerClient()
    client.pull_image("python:3.13")

    # Should make 2 requests (check + pull)
    assert mock_conn.request.call_count == 2


class TestDockerExecOperations:
  """Test container exec functionality"""

  @patch("dev_env.docker.UnixHTTPConnection")
  def test_exec_run_complete_flow(self, mock_conn_class):
    """Test complete exec run flow"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    # Three responses: create exec, start exec, inspect exec
    responses = [
      Mock(status=201, read=lambda: json.dumps({"Id": "exec123"}).encode()),
      Mock(status=200, read=lambda: b"Command output\n"),
      Mock(status=200, read=lambda: json.dumps({"ExitCode": 0, "Running": False}).encode()),
    ]

    mock_conn.getresponse.side_effect = responses

    client = DockerClient()
    output, exit_code = client.exec_run("container123", ["echo", "test"])

    assert output == b"Command output\n"
    assert exit_code == 0
    assert mock_conn.request.call_count == 3


class TestDockerNetworkOperations:
  """Test Docker network operations"""

  @pytest.mark.parametrize(
    "operation,args,expected_path,expected_method",
    [
      ("create_network", ["test-net"], "/networks/create", "POST"),
      ("remove_network", ["test-net"], "/networks/test-net", "DELETE"),
      ("connect_container_to_network", ["test-net", "container123"], "/networks/test-net/connect", "POST"),
      ("disconnect_container_from_network", ["test-net", "container123"], "/networks/test-net/disconnect", "POST"),
    ],
  )
  @patch("dev_env.docker.UnixHTTPConnection")
  def test_network_operations(self, mock_conn_class, operation, args, expected_path, expected_method):
    """Test various network operations"""
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn

    mock_response = Mock()
    mock_response.status = 201 if operation == "create_network" else 200
    mock_response.read.return_value = json.dumps({"Id": "net123"}).encode() if operation == "create_network" else b""
    mock_conn.getresponse.return_value = mock_response

    client = DockerClient()
    getattr(client, operation)(*args)

    # Verify correct API call
    call_args = mock_conn.request.call_args
    assert call_args[0][0] == expected_method
    assert expected_path in call_args[0][1]


class TestDockerWaitOperations:
  """Test container wait/readiness operations"""

  @patch("dev_env.docker.UnixHTTPConnection")
  @patch("time.sleep")
  @patch("time.time")
  def test_wait_for_container_scenarios(self, mock_time, mock_sleep, mock_conn_class):
    """Test different wait scenarios - FIXED StopIteration"""
    scenarios = [
      # Scenario 1: Container becomes ready
      {
        "times": [0, 5, 10],
        "container_state": {"State": {"Status": "running", "StartedAt": "2024-01-01T00:00:00Z"}},
        "exec_works": True,
        "expected": True,
      },
      # Scenario 2: Timeout
      {"times": [0, 31], "container_state": {"State": {"Status": "running"}}, "exec_works": False, "expected": False},
      # Scenario 3: Container not running
      {
        "times": [0, 5],  # Need at least 2 values to avoid StopIteration
        "container_state": {"State": {"Status": "exited"}},
        "exec_works": False,
        "expected": False,
      },
    ]

    for scenario in scenarios:
      mock_conn = Mock()
      mock_conn_class.return_value = mock_conn

      # Use a generator that cycles through the times and then always returns the last value
      time_values = scenario["times"]
      time_generator = (
        time_values[i] if i < len(time_values) else time_values[-1] for i in range(100)
      )  # Large range to avoid StopIteration
      mock_time.side_effect = time_generator

      # Setup responses
      container_response = Mock(status=200, read=lambda: json.dumps(scenario["container_state"]).encode())

      if scenario["exec_works"]:
        exec_responses = [
          Mock(status=201, read=lambda: json.dumps({"Id": "exec123"}).encode()),
          Mock(status=200, read=lambda: b"ready\n"),
          Mock(status=200, read=lambda: json.dumps({"ExitCode": 0}).encode()),
        ]
        mock_conn.getresponse.side_effect = [container_response] + exec_responses
      else:
        # Return container response for each call
        mock_conn.getresponse.return_value = container_response

      client = DockerClient()
      result = client.wait_for_container_ready("container123", timeout=30)

      assert result == scenario["expected"]

      # Reset mocks for next scenario
      mock_time.reset_mock()
      mock_conn_class.reset_mock()
