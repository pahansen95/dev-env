"""Minimal Docker client using stdlib only"""

import json
import socket
import http.client
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode


class UnixHTTPConnection(http.client.HTTPConnection):
  """HTTP connection over Unix domain socket"""

  def __init__(self, unix_socket: str):
    super().__init__("localhost")
    self.unix_socket = unix_socket

  def connect(self):
    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    self.sock.connect(self.unix_socket)


class DockerClient:
  """Minimal Docker API client using only stdlib"""

  def __init__(self, socket_path: str = "/var/run/docker.sock"):
    self.socket_path = socket_path

  def _request(self, method: str, path: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Any:
    """Make HTTP request to Docker daemon"""
    conn = UnixHTTPConnection(self.socket_path)
    headers = {"Content-Type": "application/json"}

    if params:
      path = f"{path}?{urlencode(params)}"

    body = json.dumps(data).encode() if data else None

    try:
      conn.request(method, path, body, headers)
      response = conn.getresponse()
      result = response.read().decode()

      if response.status >= 400:
        error_msg = json.loads(result).get("message", "Unknown error") if result else f"HTTP {response.status}"
        raise RuntimeError(f"Docker API error: {error_msg}")

      return json.loads(result) if result else {}
    finally:
      conn.close()

  def ping(self) -> bool:
    """Check if Docker daemon is accessible"""
    try:
      self._request("GET", "/_ping")
      return True
    except Exception:
      return False

  def create_container(
    self,
    name: str,
    image: str,
    command: Optional[List[str]] = None,
    environment: Optional[Dict[str, str]] = None,
    volumes: Optional[Dict[str, Dict]] = None,
    ports: Optional[Dict[str, Any]] = None,
  ) -> str:
    """Create a new container"""
    config = {
      "Image": image,
      "Hostname": name,
      "AttachStdin": False,
      "AttachStdout": False,
      "AttachStderr": False,
      "Tty": True,
      "OpenStdin": True,
    }

    if command:
      config["Cmd"] = command

    if environment:
      config["Env"] = [f"{k}={v}" for k, v in environment.items()]

    if volumes:
      config["Volumes"] = {v: {} for v in volumes.keys()}
      config["HostConfig"] = {"Binds": [f"{k}:{v['bind']}:{v.get('mode', 'rw')}" for k, v in volumes.items()]}

    if ports:
      exposed_ports = {}
      port_bindings = {}
      for container_port, host_info in ports.items():
        exposed_ports[f"{container_port}/tcp"] = {}
        if isinstance(host_info, dict):
          port_bindings[f"{container_port}/tcp"] = [
            {"HostIp": host_info.get("HostIp", ""), "HostPort": str(host_info.get("HostPort", ""))}
          ]
      config["ExposedPorts"] = exposed_ports
      if "HostConfig" not in config:
        config["HostConfig"] = {}
      config["HostConfig"]["PortBindings"] = port_bindings

    result = self._request("POST", "/containers/create", data=config, params={"name": name})
    return result["Id"]

  def start_container(self, container_id: str) -> None:
    """Start a container"""
    self._request("POST", f"/containers/{container_id}/start")

  def stop_container(self, container_id: str, timeout: int = 10) -> None:
    """Stop a container"""
    self._request("POST", f"/containers/{container_id}/stop", params={"t": timeout})

  def remove_container(self, container_id: str, force: bool = False) -> None:
    """Remove a container"""
    self._request("DELETE", f"/containers/{container_id}", params={"force": force})

  def get_container(self, container_id: str) -> Dict[str, Any]:
    """Get container details"""
    return self._request("GET", f"/containers/{container_id}/json")

  def list_containers(self, all: bool = False) -> List[Dict[str, Any]]:
    """List containers"""
    return self._request("GET", "/containers/json", params={"all": all})

  def pull_image(self, image: str) -> None:
    """Pull an image from registry"""
    # For simplicity, we'll just check if image exists
    try:
      self._request("GET", f"/images/{image}/json")
    except RuntimeError:
      # In a real implementation, we'd stream the pull response
      raise RuntimeError(f"Image {image} not found. Manual pull required.")

  def create_volume(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Create a named volume"""
    data = {"Name": name}
    if labels:
      data["Labels"] = labels
    return self._request("POST", "/volumes/create", data=data)

  def remove_volume(self, name: str) -> None:
    """Remove a volume"""
    self._request("DELETE", f"/volumes/{name}")

  def list_volumes(self) -> List[Dict[str, Any]]:
    """List all volumes"""
    result = self._request("GET", "/volumes")
    return result.get("Volumes", [])
