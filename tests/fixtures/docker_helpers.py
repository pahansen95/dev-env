"""Test helpers for Docker API mocking"""

import json
from unittest.mock import Mock
from typing import Any, Dict, List


class DockerTestHelper:
  """Helper class for creating Docker API response mocks"""

  @staticmethod
  def mock_successful_response(data: Any) -> Mock:
    """Create a successful API response mock"""
    response = Mock()
    response.status = 200
    response.read.return_value = json.dumps(data).encode() if data else b""
    return response

  @staticmethod
  def mock_error_response(status: int, message: str) -> Mock:
    """Create an error API response mock"""
    response = Mock()
    response.status = status
    response.read.return_value = json.dumps({"message": message}).encode()
    return response

  @staticmethod
  def mock_streaming_response(lines: List[str]) -> Mock:
    """Create a streaming response mock for image pulls"""
    response = Mock()
    response.status = 200
    # Mock the iter_content method for streaming
    response.iter_content.return_value = [line.encode() + b"\n" for line in lines]
    return response

  @staticmethod
  def mock_container_info(
    container_id: str = "test123", name: str = "test-container", state: str = "running", image: str = "python:3.13"
  ) -> Dict[str, Any]:
    """Create mock container information"""
    return {
      "Id": container_id,
      "Names": [f"/{name}"],
      "Image": image,
      "ImageID": f"sha256:{container_id}",
      "State": state,
      "Status": "Up 5 minutes" if state == "running" else "Exited (0) 2 minutes ago",
      "Ports": [],
      "Labels": {},
      "SizeRw": 12345,
      "SizeRootFs": 987654321,
      "HostConfig": {"NetworkMode": "default"},
      "NetworkSettings": {
        "Networks": {
          "bridge": {
            "IPAMConfig": None,
            "Links": None,
            "Aliases": None,
            "NetworkID": "abc123",
            "EndpointID": "def456",
            "Gateway": "172.17.0.1",
            "IPAddress": "172.17.0.2",
            "IPPrefixLen": 16,
            "IPv6Gateway": "",
            "GlobalIPv6Address": "",
            "GlobalIPv6PrefixLen": 0,
            "MacAddress": "02:42:ac:11:00:02",
          }
        }
      },
      "Mounts": [],
    }

  @staticmethod
  def mock_image_info(image_id: str = "python:3.13") -> Dict[str, Any]:
    """Create mock image information"""
    return {
      "Id": f"sha256:{'a' * 64}",
      "RepoTags": [image_id],
      "RepoDigests": [f"{image_id}@sha256:{'b' * 64}"],
      "Parent": "",
      "Comment": "",
      "Created": "2024-01-01T00:00:00.000000000Z",
      "Container": "",
      "DockerVersion": "24.0.0",
      "Author": "",
      "Config": {
        "Hostname": "",
        "Domainname": "",
        "User": "",
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": False,
        "OpenStdin": False,
        "StdinOnce": False,
        "Env": ["PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"],
        "Cmd": ["python3"],
        "Image": "sha256:parent123",
        "Volumes": None,
        "WorkingDir": "",
        "Entrypoint": None,
        "OnBuild": None,
        "Labels": None,
      },
      "Architecture": "amd64",
      "Os": "linux",
      "Size": 987654321,
      "VirtualSize": 987654321,
    }

  @staticmethod
  def mock_network_info(network_name: str = "test-network") -> Dict[str, Any]:
    """Create mock network information"""
    return {
      "Name": network_name,
      "Id": f"net{'a' * 59}",
      "Created": "2024-01-01T00:00:00.000000000Z",
      "Scope": "local",
      "Driver": "bridge",
      "EnableIPv6": False,
      "IPAM": {"Driver": "default", "Options": {}, "Config": [{"Subnet": "172.18.0.0/16", "Gateway": "172.18.0.1"}]},
      "Internal": False,
      "Attachable": False,
      "Ingress": False,
      "ConfigFrom": {"Network": ""},
      "ConfigOnly": False,
      "Containers": {},
      "Options": {},
      "Labels": {},
    }

  @staticmethod
  def mock_volume_info(volume_name: str = "test-volume") -> Dict[str, Any]:
    """Create mock volume information"""
    return {
      "CreatedAt": "2024-01-01T00:00:00Z",
      "Driver": "local",
      "Labels": {},
      "Mountpoint": f"/var/lib/docker/volumes/{volume_name}/_data",
      "Name": volume_name,
      "Options": {},
      "Scope": "local",
    }


class DockerClientMock:
  """Mock Docker client for testing"""

  def __init__(self):
    self.connection = Mock()
    self.containers = {}
    self.images = {}
    self.networks = {}
    self.volumes = {}

  def setup_container_responses(self, containers: List[Dict[str, Any]]):
    """Setup mock responses for container operations"""
    self.containers = {c["Id"]: c for c in containers}

    # Mock list containers
    self.connection.getresponse.return_value = DockerTestHelper.mock_successful_response(containers)

  def setup_single_container_response(self, container: Dict[str, Any]):
    """Setup mock response for single container operations"""
    self.connection.getresponse.return_value = DockerTestHelper.mock_successful_response(container)

  def setup_error_response(self, status: int, message: str):
    """Setup mock error response"""
    self.connection.getresponse.return_value = DockerTestHelper.mock_error_response(status, message)

  def setup_create_container_response(self, container_id: str):
    """Setup mock response for container creation"""
    response_data = {"Id": container_id, "Warnings": []}
    self.connection.getresponse.return_value = DockerTestHelper.mock_successful_response(response_data)

  def setup_exec_response(self, output: bytes, exit_code: int = 0):
    """Setup mock response for exec operations"""
    # Mock exec creation
    exec_id = "exec123"
    create_response = DockerTestHelper.mock_successful_response({"Id": exec_id})

    # Mock exec start - returns the output
    start_response = Mock()
    start_response.status = 200
    start_response.read.return_value = output

    # Mock exec inspect to get exit code
    inspect_response = DockerTestHelper.mock_successful_response({"ExitCode": exit_code, "Running": False})

    self.connection.getresponse.side_effect = [create_response, start_response, inspect_response]


def create_mock_docker_client() -> DockerClientMock:
  """Create a configured mock Docker client"""
  return DockerClientMock()


def mock_docker_connection():
  """Create a mock Docker connection for patching"""
  mock_conn = Mock()
  mock_conn_class = Mock(return_value=mock_conn)
  return mock_conn_class, mock_conn
