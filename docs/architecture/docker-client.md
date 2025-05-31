# Docker Client Implementation

This document details the zero-dependency Docker client implementation that forms the core of dev-env's container management capabilities.

## Design Goals

The Docker client was designed with specific constraints and goals:

1. **Zero External Dependencies**: Use only Python standard library
2. **Minimal API Surface**: Implement only required Docker endpoints
3. **Unix Socket Communication**: Direct communication with Docker daemon
4. **Robust Error Handling**: Clear error messages and recovery
5. **Type Safety**: Full type hints for all methods

## Architecture

### Component Overview

```
DockerClient
     │
     ├── UnixHTTPConnection
     │   └── Unix Socket → HTTP/1.1
     │
     ├── Request Builder
     │   ├── JSON Serialization
     │   ├── URL Parameters
     │   └── Headers
     │
     ├── Response Handler
     │   ├── JSON Parsing
     │   ├── Error Detection
     │   └── Stream Processing
     │
     └── API Methods
         ├── Container Operations
         ├── Image Management
         ├── Volume Control
         └── Network Creation
```

## Implementation Details

### Unix Socket HTTP Connection

The foundation is a custom HTTP connection over Unix domain sockets:

```python
class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP connection over Unix domain socket"""
    
    def __init__(self, unix_socket: str):
        super().__init__("localhost")
        self.unix_socket = unix_socket
    
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.unix_socket)
```

**Key Points:**
- Inherits from `http.client.HTTPConnection`
- Overrides `connect()` to use Unix socket
- Maintains HTTP/1.1 compatibility
- No external dependencies

### Request/Response Flow

```
1. Python Method Call
        ↓
2. Build HTTP Request
   - Method (GET/POST/DELETE)
   - Path (/v1.41/containers/...)
   - Headers (Content-Type: application/json)
   - Body (JSON payload)
        ↓
3. Send via Unix Socket
   - Connect to /var/run/docker.sock
   - Send HTTP/1.1 request
   - Wait for response
        ↓
4. Parse Response
   - Read status code
   - Parse JSON body
   - Handle errors
        ↓
5. Return Python Objects
```

### Core Request Method

```python
def _request(self, method: str, path: str, data: dict | None = None, params: dict | None = None) -> Any:
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
```

**Error Handling Strategy:**
- HTTP status codes ≥ 400 are errors
- Extract error message from JSON response
- Provide fallback error messages
- Always close connection

## Docker API Subset

### Implemented Endpoints

Dev-env implements a minimal subset of the Docker API:

#### Container Management
- `POST /containers/create` - Create container
- `POST /containers/{id}/start` - Start container
- `POST /containers/{id}/stop` - Stop container  
- `DELETE /containers/{id}` - Remove container
- `GET /containers/{id}/json` - Inspect container
- `POST /containers/{id}/exec` - Execute command

#### Image Management
- `POST /images/create` - Pull image
- `GET /images/{name}/json` - Inspect image

#### Volume Management
- `POST /volumes/create` - Create volume
- `DELETE /volumes/{name}` - Remove volume

#### Network Management
- `POST /networks/create` - Create network
- `DELETE /networks/{id}` - Remove network

### API Version Compatibility

Dev-env targets Docker API v1.41 (Docker 20.10+):

```python
# API version negotiation not implemented
# Assumes Docker 20.10+ which is widely available
API_VERSION = "v1.41"
BASE_URL = f"/{API_VERSION}"
```

## Container Creation Deep Dive

### Request Structure

Creating a container involves a complex JSON payload:

```python
def create_container(self, name: str, image: str, **kwargs) -> str:
    config = {
        "Image": image,
        "Hostname": name,
        "AttachStdin": False,
        "AttachStdout": False,
        "AttachStderr": False,
        "Tty": True,
        "OpenStdin": True,
    }
    
    # Security configuration
    if env_config:
        config["User"] = env_config.user
        
        if env_config.no_new_privileges:
            config["SecurityOpt"] = ["no-new-privileges:true"]
        
        if env_config.read_only_root_fs:
            config["ReadonlyRootfs"] = True
    
    # Environment variables
    if environment:
        config["Env"] = [f"{k}={v}" for k, v in environment.items()]
    
    # Volume mounts
    if volumes:
        config["Volumes"] = volumes
    
    # Port exposure
    if ports:
        config["ExposedPorts"] = {
            f"{port}/tcp": {} for port in ports.keys()
        }
    
    # Host configuration
    host_config = {
        "AutoRemove": False,
        "NetworkMode": network or "bridge"
    }
    
    # Port bindings
    if ports:
        host_config["PortBindings"] = {}
        for container_port, host_config_dict in ports.items():
            host_config["PortBindings"][f"{container_port}/tcp"] = [
                {"HostPort": str(host_config_dict.get("HostPort", container_port))}
            ]
    
    # Volume bindings
    if volumes:
        host_config["Binds"] = []
        for mount_path, mount_config in volumes.items():
            if mount_config.get("bind"):
                bind_str = f"{mount_config['bind']}:{mount_path}"
                if mount_config.get("mode"):
                    bind_str += f":{mount_config['mode']}"
                host_config["Binds"].append(bind_str)
    
    config["HostConfig"] = host_config
```

### Response Handling

```python
response = self._request(
    "POST",
    "/containers/create",
    data=config,
    params={"name": container_name}
)

# Extract container ID from response
return response["Id"]
```

## Image Pull Implementation

### Streaming Progress

Image pulls use chunked transfer encoding:

```python
def pull_image(self, image: str, progress_callback: Callable | None = None) -> None:
    conn = UnixHTTPConnection(self.socket_path)
    
    params = {"fromImage": image}
    path = f"/images/create?{urlencode(params)}"
    
    conn.request("POST", path)
    response = conn.getresponse()
    
    if response.status != 200:
        raise RuntimeError(f"Failed to pull image: HTTP {response.status}")
    
    # Process streaming response
    for line in response:
        if not line:
            continue
            
        try:
            data = json.loads(line.decode().strip())
            
            if "error" in data:
                raise RuntimeError(f"Pull error: {data['error']}")
            
            if progress_callback and "progress" in data:
                # Parse progress like "[==>    ] 10.5MB/50MB"
                progress_callback(data.get("status", ""), parse_progress(data["progress"]))
                
        except json.JSONDecodeError:
            continue
```

**Progress Parsing:**
```python
def parse_progress(progress_str: str) -> float:
    # Extract "10.5MB/50MB" format
    match = re.search(r'(\d+\.?\d*)([KMG]B)?/(\d+\.?\d*)([KMG]B)?', progress_str)
    if match:
        current = parse_size(match.group(1), match.group(2))
        total = parse_size(match.group(3), match.group(4))
        return (current / total) * 100 if total > 0 else 0
    return 0.0
```

## Command Execution

### Exec Create and Start

Executing commands in containers is a two-step process:

```python
def exec_run(self, container_id: str, cmd: list[str], **kwargs) -> tuple[str, int]:
    # Step 1: Create exec instance
    exec_config = {
        "AttachStdin": False,
        "AttachStdout": True,
        "AttachStderr": True,
        "Tty": False,
        "Cmd": cmd
    }
    
    if "user" in kwargs:
        exec_config["User"] = kwargs["user"]
    
    if "workdir" in kwargs:
        exec_config["WorkingDir"] = kwargs["workdir"]
    
    exec_resp = self._request(
        "POST",
        f"/containers/{container_id}/exec",
        data=exec_config
    )
    exec_id = exec_resp["Id"]
    
    # Step 2: Start exec instance
    start_config = {
        "Detach": False,
        "Tty": False
    }
    
    # Use raw socket for output streaming
    conn = UnixHTTPConnection(self.socket_path)
    conn.request(
        "POST",
        f"/exec/{exec_id}/start",
        body=json.dumps(start_config).encode(),
        headers={"Content-Type": "application/json"}
    )
    
    response = conn.getresponse()
    output = response.read().decode()
    
    # Get exit code
    inspect_resp = self._request("GET", f"/exec/{exec_id}/json")
    exit_code = inspect_resp.get("ExitCode", 0)
    
    return output, exit_code
```

## Error Handling Patterns

### Connection Errors

```python
try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(self.socket_path)
    sock.close()
except FileNotFoundError:
    raise DockerError("Docker socket not found. Is Docker installed?")
except PermissionError:
    raise DockerError("Permission denied accessing Docker socket. Add user to docker group.")
except ConnectionRefusedError:
    raise DockerError("Cannot connect to Docker daemon. Is it running?")
```

### API Errors

Docker API errors follow a consistent pattern:

```json
{
    "message": "No such container: mycontainer",
    "error": "Container not found"
}
```

Error extraction:
```python
if response.status == 404:
    error_data = json.loads(response_body)
    if "container" in path:
        raise ContainerNotFoundError(error_data["message"])
    elif "image" in path:
        raise ImageNotFoundError(error_data["message"])
    else:
        raise NotFoundError(error_data["message"])
```

## Performance Optimizations

### Connection Reuse

While the current implementation creates a new connection per request, connection reuse could be implemented:

```python
class DockerClient:
    def __init__(self):
        self._conn = None
    
    def _get_connection(self):
        if self._conn is None or not self._is_connected():
            self._conn = UnixHTTPConnection(self.socket_path)
            self._conn.connect()
        return self._conn
```

### Request Batching

Multiple operations can be optimized:

```python
def create_environment(self, config):
    # Batch network and volume creation
    tasks = []
    
    if config.network:
        tasks.append(("network", self.create_network, config.network))
    
    for volume in config.volumes:
        if volume.is_named_volume():
            tasks.append(("volume", self.create_volume, volume.name))
    
    # Execute in parallel (simplified)
    for task_type, func, arg in tasks:
        try:
            func(arg)
        except AlreadyExistsError:
            pass  # Idempotent
```

## Testing Considerations

### Mock Docker Daemon

For testing without Docker:

```python
class MockDockerDaemon:
    def __init__(self):
        self.containers = {}
        self.images = set()
        self.volumes = {}
    
    def handle_request(self, method, path, data):
        if path.startswith("/containers/create"):
            return self.create_container(data)
        elif path.startswith("/containers/") and "/start" in path:
            return self.start_container(path)
        # ... more endpoints
```

### Integration Tests

Real Docker daemon tests:

```python
def test_container_lifecycle():
    client = DockerClient()
    
    # Create
    container_id = client.create_container(
        name="test-container",
        image="alpine:latest",
        command=["sleep", "10"]
    )
    
    # Start
    client.start_container(container_id)
    
    # Verify running
    info = client.inspect_container(container_id)
    assert info["State"]["Running"]
    
    # Cleanup
    client.stop_container(container_id)
    client.remove_container(container_id)
```

## Limitations and Trade-offs

### Current Limitations

1. **No Streaming Logs**: Log following not implemented
2. **No Build Support**: Cannot build images
3. **Limited Exec**: No interactive exec sessions
4. **No Swarm/Compose**: Single container focus

### Design Trade-offs

1. **Simplicity over Features**: Minimal API surface
2. **Synchronous Only**: No async support
3. **JSON Only**: No binary data handling
4. **Unix Socket Only**: No TCP/TLS support

### Future Considerations

Potential enhancements while maintaining zero dependencies:

1. **Connection Pooling**: Reuse socket connections
2. **Streaming Support**: Implement chunked transfer for logs
3. **Binary Protocol**: Support for `docker attach`
4. **Windows Support**: Named pipe implementation

## Security Considerations

### Socket Security

```python
# Verify socket permissions
def check_docker_socket_security():
    socket_path = Path("/var/run/docker.sock")
    
    if not socket_path.exists():
        raise SecurityError("Docker socket not found")
    
    stat = socket_path.stat()
    if stat.st_mode & 0o007:  # World accessible
        raise SecurityError("Docker socket is world accessible!")
```

### Request Validation

All requests are validated before sending:

```python
def validate_container_config(config):
    # Prevent privileged containers
    if config.get("Privileged"):
        raise SecurityError("Privileged containers not allowed")
    
    # Validate user
    if config.get("User") == "root" or config.get("User") == "0":
        raise SecurityError("Root user not allowed")
```

## Conclusion

The zero-dependency Docker client provides a robust foundation for container management while maintaining simplicity and security. By implementing only the required subset of the Docker API, the client remains maintainable and understandable while providing all necessary functionality for development environment management.

For related architectural components, see:
- [Architecture Overview](overview.md)
- [State Management](state-management.md)
- [Container Lifecycle](container-lifecycle.md)