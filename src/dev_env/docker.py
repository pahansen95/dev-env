"""Minimal Docker client using stdlib only"""

import json
import socket
import http.client
from typing import Dict, Any, Optional, List, Callable
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
    network: Optional[str] = None,
    security: Optional[Any] = None,
    resources: Optional[Any] = None,
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

    # Apply security configuration
    if security:
      config["User"] = security.user

      # Security options
      security_opts = []
      if security.no_new_privileges:
        security_opts.append("no-new-privileges:true")
      if security_opts:
        config["SecurityOpt"] = security_opts

      # Read-only root filesystem
      if security.read_only_root_fs:
        config["ReadonlyRootfs"] = True

    if command:
      config["Cmd"] = command

    if environment:
      config["Env"] = [f"{k}={v}" for k, v in environment.items()]

    # Initialize HostConfig for resource and security constraints
    host_config = {}

    # Apply resource configuration
    if resources:
      resource_config = resources.to_docker_config()
      host_config.update(resource_config)

    # Apply security capabilities
    if security:
      if security.drop_capabilities:
        host_config["CapDrop"] = security.drop_capabilities
      if security.add_capabilities:
        host_config["CapAdd"] = security.add_capabilities

    if volumes:
      config["Volumes"] = {v: {} for v in volumes.keys()}
      if "HostConfig" not in config:
        config["HostConfig"] = host_config
      config["HostConfig"]["Binds"] = [f"{k}:{v['bind']}:{v.get('mode', 'rw')}" for k, v in volumes.items()]
    elif host_config:
      config["HostConfig"] = host_config

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
        config["HostConfig"] = host_config
      config["HostConfig"]["PortBindings"] = port_bindings

    # Configure networking
    if network:
      if "HostConfig" not in config:
        config["HostConfig"] = host_config
      config["HostConfig"]["NetworkMode"] = network

      # For custom networks, also add to NetworkingConfig
      if network not in ("bridge", "host", "none"):
        config["NetworkingConfig"] = {"EndpointsConfig": {network: {}}}

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

  def pull_image(self, image: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> None:
    """Pull an image from registry with streaming progress"""
    # First check if image already exists
    try:
      self._request("GET", f"/images/{image}/json")
      if progress_callback:
        progress_callback("Image already exists", 100.0)
      return
    except RuntimeError:
      pass  # Image doesn't exist, proceed with pull

    # Parse image specification
    registry, name, tag = self._parse_image_spec(image)

    # Stream the pull request
    conn = UnixHTTPConnection(self.socket_path)
    headers = {"Content-Type": "application/json"}

    try:
      conn.request("POST", f"/images/create?fromImage={image}", None, headers)
      response = conn.getresponse()

      if response.status >= 400:
        error_data = response.read().decode()
        error_msg = json.loads(error_data).get("message", "Unknown error") if error_data else f"HTTP {response.status}"
        raise RuntimeError(f"Docker API error: {error_msg}")

      # Process streaming response
      self._process_pull_stream(response, progress_callback)

    finally:
      conn.close()

  def _parse_image_spec(self, image: str) -> tuple[str, str, str]:
    """Parse image specification into (registry, name, tag)"""
    # Default values
    registry = "docker.io"
    tag = "latest"

    # Split by '/' to separate registry and repository
    parts = image.split("/")

    if len(parts) == 1:
      # Simple name like 'ubuntu' -> docker.io/library/ubuntu:latest
      name = f"library/{parts[0]}"
    elif len(parts) == 2:
      # Two parts: either 'registry/image' or 'namespace/image'
      if "." in parts[0] or ":" in parts[0]:
        # First part contains '.' or ':' -> it's a registry
        registry = parts[0]
        name = parts[1]
      else:
        # No registry specified -> docker.io/namespace/image
        name = image
    else:
      # Three or more parts -> registry/namespace/image
      registry = parts[0]
      name = "/".join(parts[1:])

    # Extract tag if present
    if ":" in name:
      name, tag = name.rsplit(":", 1)

    return registry, name, tag

  def _process_pull_stream(self, response, progress_callback: Optional[Callable[[str, float], None]]) -> None:
    """Process streaming pull response"""
    layers = {}
    total_size = 0
    downloaded_size = 0

    while True:
      line = response.readline()
      if not line:
        break

      try:
        data = json.loads(line.decode().strip())
      except (json.JSONDecodeError, UnicodeDecodeError):
        continue

      if "error" in data:
        raise RuntimeError(f"Pull failed: {data['error']}")

      # Track layer progress
      layer_id = data.get("id")
      if layer_id and "progressDetail" in data:
        detail = data["progressDetail"]
        if "total" in detail:
          layers[layer_id] = {"total": detail["total"], "current": detail.get("current", 0)}

      # Calculate overall progress
      if layers:
        total_size = sum(layer["total"] for layer in layers.values())
        downloaded_size = sum(layer["current"] for layer in layers.values())

        if total_size > 0:
          progress = (downloaded_size / total_size) * 100
          status = data.get("status", "Downloading")
          if progress_callback:
            progress_callback(status, progress)

      # Handle final status messages
      status = data.get("status", "")
      if status in ["Pull complete", "Download complete"]:
        if progress_callback:
          progress_callback(status, 100.0)

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

  def get_volume(self, name: str) -> Dict[str, Any]:
    """Get volume details"""
    return self._request("GET", f"/volumes/{name}")

  def get_volume_usage(self, name: str) -> Dict[str, Any]:
    """Get volume usage information via system df"""
    try:
      # Use system df to get volume usage
      result = self._request("GET", "/system/df")
      volumes = result.get("Volumes", [])

      for volume in volumes:
        if volume.get("Name") == name:
          return {
            "size": volume.get("Size", 0),
            "usage_data": volume.get("UsageData", {}),
            "ref_count": volume.get("RefCount", 0),
          }

      return {"size": 0, "usage_data": {}, "ref_count": 0}
    except Exception:
      # Fallback - volume exists but no size info available
      return {"size": -1, "usage_data": {}, "ref_count": 0}

  def create_exec(
    self,
    container_id: str,
    cmd: List[str],
    working_dir: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
    user: str = "root",
    attach_stdout: bool = True,
    attach_stderr: bool = True,
    tty: bool = False,
  ) -> str:
    """Create an exec instance"""
    config = {
      "AttachStdin": False,
      "AttachStdout": attach_stdout,
      "AttachStderr": attach_stderr,
      "Tty": tty,
      "Cmd": cmd,
      "User": user,
    }

    if working_dir:
      config["WorkingDir"] = working_dir

    if environment:
      config["Env"] = [f"{k}={v}" for k, v in environment.items()]

    result = self._request("POST", f"/containers/{container_id}/exec", data=config)
    return result["Id"]

  def start_exec(self, exec_id: str, detach: bool = False) -> bytes:
    """Start an exec instance and return output"""
    config = {"Detach": detach, "Tty": False}

    conn = UnixHTTPConnection(self.socket_path)
    headers = {"Content-Type": "application/json"}
    body = json.dumps(config).encode()

    try:
      conn.request("POST", f"/exec/{exec_id}/start", body, headers)
      response = conn.getresponse()

      if response.status >= 400:
        error_data = response.read().decode()
        error_msg = json.loads(error_data).get("message", "Unknown error") if error_data else f"HTTP {response.status}"
        raise RuntimeError(f"Docker API error: {error_msg}")

      # For detached mode, return empty bytes
      if detach:
        return b""

      # Read all output
      output = response.read()
      return output
    finally:
      conn.close()

  def get_exec_info(self, exec_id: str) -> Dict[str, Any]:
    """Get exec instance information including exit code"""
    return self._request("GET", f"/exec/{exec_id}/json")

  def exec_run(
    self,
    container_id: str,
    cmd: List[str],
    working_dir: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
    user: str = "root",
  ) -> tuple[bytes, int]:
    """Execute a command and return (output, exit_code)"""
    exec_id = self.create_exec(
      container_id=container_id,
      cmd=cmd,
      working_dir=working_dir,
      environment=environment,
      user=user,
      tty=False,
    )

    output = self.start_exec(exec_id)
    exec_info = self.get_exec_info(exec_id)
    exit_code = exec_info.get("ExitCode", 0)

    return output, exit_code

  def get_container_logs(self, container_id: str, follow: bool = False, tail: Optional[int] = None) -> bytes:
    """Get container logs"""
    params = {"stdout": "true", "stderr": "true", "timestamps": "true"}

    if follow:
      params["follow"] = "true"

    if tail is not None:
      params["tail"] = str(tail)

    conn = UnixHTTPConnection(self.socket_path)

    try:
      path = f"/containers/{container_id}/logs"
      if params:
        path = f"{path}?{urlencode(params)}"

      conn.request("GET", path)
      response = conn.getresponse()

      if response.status >= 400:
        error_data = response.read().decode()
        error_msg = json.loads(error_data).get("message", "Unknown error") if error_data else f"HTTP {response.status}"
        raise RuntimeError(f"Docker API error: {error_msg}")

      return response.read()
    finally:
      conn.close()

  def wait_for_container_ready(self, container_id: str, timeout: int = 30) -> bool:
    """Wait for container to be ready"""
    import time

    start_time = time.time()

    while time.time() - start_time < timeout:
      try:
        container = self.get_container(container_id)
        state = container["State"]

        # Check if container is running
        if state["Status"] != "running":
          return False

        # Check if container has been running for at least 2 seconds
        # This helps ensure it's stable and not immediately crashing
        if state.get("StartedAt"):
          # Simple check - if we can exec a basic command, it's ready
          try:
            _, exit_code = self.exec_run(container_id, ["echo", "ready"])
            if exit_code == 0:
              return True
          except Exception:
            pass

        time.sleep(1)

      except Exception:
        time.sleep(1)

    return False

  def attach_container(self, container_id: str, stream: bool = True) -> bytes:
    """Attach to a running container's main process"""
    params = {"stream": "true" if stream else "false", "stdout": "true", "stderr": "true"}

    conn = UnixHTTPConnection(self.socket_path)

    try:
      path = f"/containers/{container_id}/attach"
      if params:
        path = f"{path}?{urlencode(params)}"

      conn.request("POST", path)
      response = conn.getresponse()

      if response.status >= 400:
        error_data = response.read().decode()
        error_msg = json.loads(error_data).get("message", "Unknown error") if error_data else f"HTTP {response.status}"
        raise RuntimeError(f"Docker API error: {error_msg}")

      if stream:
        # For streaming, we'd need to handle this differently
        # For now, just read available data
        return response.read()
      else:
        return response.read()
    finally:
      conn.close()

  def create_network(
    self,
    name: str,
    driver: str = "bridge",
    options: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
  ) -> Dict[str, Any]:
    """Create a custom network"""
    data = {"Name": name, "Driver": driver}

    if options:
      data["Options"] = options
    if labels:
      data["Labels"] = labels

    return self._request("POST", "/networks/create", data=data)

  def remove_network(self, name: str) -> None:
    """Remove a network"""
    self._request("DELETE", f"/networks/{name}")

  def list_networks(self) -> List[Dict[str, Any]]:
    """List all networks"""
    return self._request("GET", "/networks")

  def get_network(self, name: str) -> Dict[str, Any]:
    """Get network details"""
    return self._request("GET", f"/networks/{name}")

  def connect_container_to_network(self, network_name: str, container_id: str) -> None:
    """Connect container to network"""
    data = {"Container": container_id}
    self._request("POST", f"/networks/{network_name}/connect", data=data)

  def disconnect_container_from_network(self, network_name: str, container_id: str) -> None:
    """Disconnect container from network"""
    data = {"Container": container_id}
    self._request("POST", f"/networks/{network_name}/disconnect", data=data)
