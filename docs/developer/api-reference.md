# API Reference

This document provides complete module documentation for programmatic usage of dev-env.

## Core Modules

### `dev_env.config`

Configuration system using dataclasses for type-safe environment definitions.

#### Classes

##### `Environment`

Main environment configuration class.

```python
@dataclass
class Environment:
    """Development environment configuration"""
    
    name: str                           # Unique environment identifier
    base_image: str                     # Docker base image
    command: list[str] | None = None    # Container startup command
    environment: dict[str, str] | None = None  # Environment variables
    volumes: list[VolumeMount] | None = None   # Volume mounts
    ports: dict[int, Any] | None = None        # Port mappings
    git: GitConfig | None = None               # Git repository config
    ssh: SSHConfig | None = None               # SSH server config
    network: NetworkConfig | None = None       # Network configuration
    working_dir: str = "/workspace"            # Working directory
    user: str = "1000:1000"                   # Container user
    hostname: str | None = None               # Custom hostname
    security_level: SecurityLevel | None = None  # Security preset
```

**Methods:**

- `__post_init__()`: Validates configuration and applies security defaults
- `to_docker_config()`: Converts to Docker API format

**Example:**
```python
from dev_env.config import Environment, GitConfig

env = Environment(
    name="myapp",
    base_image="python:3.13",
    git=GitConfig(url="https://github.com/user/repo.git"),
    ports={8000: {"HostPort": 8000}}
)
```

##### `VolumeMount`

Volume mount configuration for persistent and bind mounts.

```python
@dataclass
class VolumeMount:
    """Volume mount configuration"""
    
    source: str                    # Source path or volume name
    target: str                    # Container mount path
    mode: str = "rw"              # Access mode: "rw" or "ro"
    name: str | None = None       # Volume name (auto-generated)
```

**Methods:**

- `is_named_volume() -> bool`: Check if this is a named volume
- `type -> str`: Get volume type ("bind" or "named")

**Example:**
```python
from dev_env.config import VolumeMount

# Bind mount
bind_mount = VolumeMount(
    source="./src",
    target="/app/src",
    mode="rw"
)

# Named volume
named_volume = VolumeMount(
    source="app-data",
    target="/app/data",
    mode="rw"
)
```

##### `GitConfig`

Git repository configuration for automatic cloning.

```python
@dataclass
class GitConfig:
    """Git repository configuration"""
    
    url: str                      # Repository URL (HTTPS or SSH)
    branch: str = "main"          # Branch to checkout
    path: str = "/workspace"      # Clone destination path
    shallow: bool = True          # Use shallow clone
```

**Example:**
```python
from dev_env.config import GitConfig

# HTTPS repository
git_config = GitConfig(
    url="https://github.com/user/repo.git",
    branch="develop",
    shallow=False
)

# SSH repository
ssh_git_config = GitConfig(
    url="git@github.com:user/private-repo.git"
)
```

##### `SSHConfig`

SSH server configuration for remote access.

```python
@dataclass
class SSHConfig:
    """SSH configuration"""
    
    port: int = 22                        # SSH port inside container
    authorized_keys: list[str] = []       # SSH public keys
    password_auth: bool = False           # Enable password auth (not recommended)
```

**Example:**
```python
from dev_env.config import SSHConfig

ssh_config = SSHConfig(
    port=22,
    authorized_keys=[
        "ssh-rsa AAAAB3NzaC1yc2E... user@host",
        "ssh-ed25519 AAAAC3NzaC1lZDI... admin@host"
    ]
)
```

##### `NetworkConfig`

Network configuration for container networking.

```python
@dataclass
class NetworkConfig:
    """Network configuration"""
    
    name: str | None = None               # Network name
    driver: str = "bridge"                # Network driver
    options: dict[str, str] | None = None # Driver options
    labels: dict[str, str] | None = None  # Network labels
```

**Example:**
```python
from dev_env.config import NetworkConfig

network = NetworkConfig(
    name="app-network",
    driver="bridge",
    options={"subnet": "172.20.0.0/16"}
)
```

##### `SecurityLevel`

Security preset enumeration.

```python
class SecurityLevel(Enum):
    """Security preset levels"""
    
    RELAXED = "relaxed"     # Compatibility mode (less secure)
    STANDARD = "standard"   # Recommended defaults
```

#### Functions

##### `load_environment(config_path: Path) -> Environment`

Load environment configuration from Python file.

**Parameters:**
- `config_path`: Path to configuration file

**Returns:**
- `Environment`: Loaded environment configuration

**Raises:**
- `ConfigError`: If configuration is invalid
- `FileNotFoundError`: If config file doesn't exist

**Example:**
```python
from dev_env.config import load_environment
from pathlib import Path

env = load_environment(Path("myproject.py"))
print(f"Loaded environment: {env.name}")
```

### `dev_env.docker`

Zero-dependency Docker client implementation using stdlib only.

#### Classes

##### `DockerClient`

Minimal Docker API client for container management.

```python
class DockerClient:
    """Minimal Docker API client using only stdlib"""
    
    def __init__(self, socket_path: str = "/var/run/docker.sock"):
        self.socket_path = socket_path
```

**Methods:**

##### `ping() -> bool`

Check if Docker daemon is accessible.

**Returns:**
- `bool`: True if Docker is available

**Example:**
```python
from dev_env.docker import DockerClient

docker = DockerClient()
if docker.ping():
    print("Docker is available")
else:
    print("Docker is not accessible")
```

##### `create_container(name, image, **kwargs) -> str`

Create a new container.

**Parameters:**
- `name: str`: Container name
- `image: str`: Docker image name
- `command: list[str] | None`: Startup command
- `environment: dict[str, str] | None`: Environment variables
- `volumes: dict[str, dict] | None`: Volume mounts
- `ports: dict[str, Any] | None`: Port mappings
- `network: str | None`: Network name
- `env_config: Any | None`: Environment config object

**Returns:**
- `str`: Container ID

**Example:**
```python
container_id = docker.create_container(
    name="myapp",
    image="python:3.13",
    command=["python", "app.py"],
    environment={"DEBUG": "true"},
    ports={"8000/tcp": {"HostPort": "8000"}}
)
```

##### `start_container(container_id: str) -> None`

Start an existing container.

**Parameters:**
- `container_id: str`: Container ID to start

##### `stop_container(container_id: str) -> None`

Stop a running container.

**Parameters:**
- `container_id: str`: Container ID to stop

##### `remove_container(container_id: str, force: bool = False) -> None`

Remove a container.

**Parameters:**
- `container_id: str`: Container ID to remove
- `force: bool`: Force removal of running container

##### `exec_run(container_id: str, cmd: list[str], **kwargs) -> tuple[str, int]`

Execute command in running container.

**Parameters:**
- `container_id: str`: Container ID
- `cmd: list[str]`: Command to execute
- `user: str | None`: User to run as
- `workdir: str | None`: Working directory

**Returns:**
- `tuple[str, int]`: Output and exit code

**Example:**
```python
output, exit_code = docker.exec_run(
    container_id,
    ["python", "--version"],
    user="dev"
)
print(f"Python version: {output}")
```

##### `pull_image(image: str, progress_callback: Callable | None = None) -> None`

Pull Docker image with optional progress callback.

**Parameters:**
- `image: str`: Image name to pull
- `progress_callback: Callable | None`: Progress callback function

**Example:**
```python
def progress(status: str, progress: float):
    print(f"{status}: {progress:.1f}%")

docker.pull_image("python:3.13", progress)
```

##### `create_volume(name: str) -> None`

Create a named volume.

**Parameters:**
- `name: str`: Volume name

##### `remove_volume(name: str) -> None`

Remove a named volume.

**Parameters:**
- `name: str`: Volume name

##### `create_network(name: str, driver: str = "bridge", **options) -> None`

Create a Docker network.

**Parameters:**
- `name: str`: Network name
- `driver: str`: Network driver
- `**options`: Additional network options

### `dev_env.state`

SQLite-based state management for environment tracking.

#### Classes

##### `StateManager`

Manage environment state persistence.

```python
class StateManager:
    """Manage environment state using SQLite"""
    
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.db_path = state_dir / "environments.db"
```

**Methods:**

##### `save_environment(name: str, state: dict[str, Any]) -> None`

Save environment state to database.

**Parameters:**
- `name: str`: Environment name
- `state: dict`: Environment state data

**Example:**
```python
from dev_env.state import StateManager
from pathlib import Path

state_manager = StateManager(Path("~/.dev-env/state"))

state_manager.save_environment("myapp", {
    "container_id": "abc123",
    "container_name": "devenv-myapp-abc123",
    "config": {"image": "python:3.13"},
    "volumes": ["myapp-data"],
    "network": "myapp-network"
})
```

##### `get_environment(name: str) -> dict[str, Any] | None`

Retrieve environment state by name.

**Parameters:**
- `name: str`: Environment name

**Returns:**
- `dict | None`: Environment state or None if not found

##### `list_environments() -> list[dict[str, Any]]`

List all managed environments.

**Returns:**
- `list[dict]`: List of environment states

##### `remove_environment(name: str) -> None`

Remove environment from state tracking.

**Parameters:**
- `name: str`: Environment name to remove

##### `cleanup_orphaned_state() -> int`

Remove state entries for non-existent containers.

**Returns:**
- `int`: Number of orphaned entries removed

### `dev_env.utils`

Utility functions for Docker operations and validation.

#### Functions

##### `check_docker_available() -> bool`

Check if Docker daemon is accessible.

**Returns:**
- `bool`: True if Docker socket is accessible

##### `generate_container_name(env_name: str) -> str`

Generate unique container name with timestamp hash.

**Parameters:**
- `env_name: str`: Environment name

**Returns:**
- `str`: Unique container name

##### `validate_port_mappings(ports: dict[int, Any]) -> list[str]`

Validate port mapping configuration.

**Parameters:**
- `ports: dict`: Port mapping configuration

**Returns:**
- `list[str]`: List of validation warnings

##### `validate_bind_mounts(volumes: list) -> list[str]`

Validate volume mount configuration.

**Parameters:**
- `volumes: list`: Volume mount list

**Returns:**
- `list[str]`: List of validation warnings

##### `apply_security_defaults(environment) -> None`

Apply security defaults and validate configuration.

**Parameters:**
- `environment`: Environment configuration object

**Raises:**
- `ConfigError`: If security violations are detected

##### `setup_ssh_server(docker_client, container_id: str) -> None`

Configure SSH server in container.

**Parameters:**
- `docker_client`: Docker client instance
- `container_id: str`: Container ID

##### `inject_ssh_key(docker_client, container_id: str, public_key: str) -> None`

Inject SSH public key into container.

**Parameters:**
- `docker_client`: Docker client instance
- `container_id: str`: Container ID
- `public_key: str`: SSH public key content

##### `get_host_ssh_key() -> str`

Get or generate host SSH public key.

**Returns:**
- `str`: SSH public key content

#### Exception Classes

##### `DevEnvError`

Base exception for dev-env errors.

```python
class DevEnvError(Exception):
    """Base exception for dev-env errors"""
    
    def __init__(self, message: str, details: str = "", exit_code: int = 1):
        self.message = message
        self.details = details
        self.exit_code = exit_code
    
    def format_error(self) -> str:
        """Format error message for display"""
```

##### `ConfigError`

Configuration-related errors.

```python
class ConfigError(DevEnvError):
    """Configuration errors"""
    
    @classmethod
    def environment_exists(cls, name: str):
        """Environment already exists error"""
    
    @classmethod
    def ssh_not_enabled(cls, env_name: str):
        """SSH not enabled error"""
    
    @classmethod
    def security_violation(cls, message: str):
        """Security violation error"""
```

##### `DockerError`

Docker-related errors.

```python
class DockerError(DevEnvError):
    """Docker operation errors"""
    
    @classmethod
    def daemon_unavailable(cls):
        """Docker daemon unavailable error"""
    
    @classmethod
    def container_not_found(cls, container_id: str):
        """Container not found error"""
```

## Usage Examples

### Basic Programmatic Usage

```python
#!/usr/bin/env python3
"""Example: Create and manage environments programmatically"""

from pathlib import Path
from dev_env.config import Environment, GitConfig, VolumeMount
from dev_env.docker import DockerClient
from dev_env.state import StateManager
from dev_env.utils import generate_container_name, setup_ssh_server

def create_environment(name: str, repo_url: str) -> str:
    """Create and start a development environment"""
    
    # Define environment configuration
    env = Environment(
        name=name,
        base_image="python:3.13",
        git=GitConfig(url=repo_url),
        ports={
            22: {"HostPort": 2222},
            8000: {"HostPort": 8000}
        },
        volumes=[
            VolumeMount(source=".", target="/app"),
            VolumeMount(
                source=f"{name}-cache",
                target="/root/.cache",
                mode="rw"
            )
        ]
    )
    
    # Initialize clients
    docker = DockerClient()
    state_manager = StateManager(Path("~/.dev-env/state"))
    
    # Generate unique container name
    container_name = generate_container_name(name)
    
    # Create container
    container_id = docker.create_container(
        name=container_name,
        image=env.base_image,
        command=env.command,
        environment=env.environment,
        ports=env.ports,
        volumes=env.volumes
    )
    
    # Start container
    docker.start_container(container_id)
    
    # Setup SSH if configured
    if env.ssh or 22 in (env.ports or {}):
        setup_ssh_server(docker, container_id)
    
    # Save state
    state_manager.save_environment(name, {
        "container_id": container_id,
        "container_name": container_name,
        "config": env.__dict__,
        "volumes": [v.name for v in (env.volumes or []) if v.is_named_volume()],
        "network": env.network.name if env.network else None
    })
    
    return container_id

# Usage
container_id = create_environment(
    "myapp",
    "https://github.com/user/myapp.git"
)
print(f"Environment created: {container_id}")
```

### Configuration Templates

```python
#!/usr/bin/env python3
"""Example: Configuration template system"""

from dev_env.config import Environment, GitConfig, VolumeMount, NetworkConfig
from typing import Dict, Any

class EnvironmentTemplate:
    """Base class for environment templates"""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
    
    def create_environment(self, **kwargs) -> Environment:
        """Override in subclasses"""
        raise NotImplementedError

class PythonWebTemplate(EnvironmentTemplate):
    """Template for Python web applications"""
    
    def create_environment(
        self,
        repo_url: str,
        python_version: str = "3.13",
        port: int = 8000,
        **kwargs
    ) -> Environment:
        
        return Environment(
            name=self.project_name,
            base_image=f"python:{python_version}",
            git=GitConfig(url=repo_url),
            ports={
                22: {"HostPort": 2222},
                port: {"HostPort": port}
            },
            volumes=[
                VolumeMount(source=".", target="/app"),
                VolumeMount(
                    source=f"{self.project_name}-pip-cache",
                    target="/root/.cache/pip",
                    mode="rw"
                )
            ],
            environment={
                "PYTHONUNBUFFERED": "1",
                "DEBUG": "true",
                **kwargs.get("environment", {})
            }
        )

class NodeWebTemplate(EnvironmentTemplate):
    """Template for Node.js web applications"""
    
    def create_environment(
        self,
        repo_url: str,
        node_version: str = "20",
        **kwargs
    ) -> Environment:
        
        return Environment(
            name=self.project_name,
            base_image=f"node:{node_version}",
            git=GitConfig(url=repo_url),
            ports={
                22: {"HostPort": 2222},
                3000: {"HostPort": 3000}
            },
            volumes=[
                VolumeMount(source=".", target="/app"),
                VolumeMount(
                    source=f"{self.project_name}-node-modules",
                    target="/app/node_modules",
                    mode="rw"
                )
            ],
            environment={
                "NODE_ENV": "development",
                "CHOKIDAR_USEPOLLING": "true"
            }
        )

# Usage
python_template = PythonWebTemplate("myapi")
python_env = python_template.create_environment(
    repo_url="https://github.com/user/api.git",
    environment={"DATABASE_URL": "sqlite:///app.db"}
)

node_template = NodeWebTemplate("myfrontend")
node_env = node_template.create_environment(
    repo_url="https://github.com/user/frontend.git"
)
```

### State Management

```python
#!/usr/bin/env python3
"""Example: Environment state management"""

from pathlib import Path
from dev_env.state import StateManager
from dev_env.docker import DockerClient

def cleanup_environments():
    """Clean up orphaned environments"""
    
    state_manager = StateManager(Path("~/.dev-env/state"))
    docker = DockerClient()
    
    # Get all managed environments
    environments = state_manager.list_environments()
    
    print(f"Found {len(environments)} managed environments")
    
    # Check each environment
    orphaned = []
    for env in environments:
        container_id = env["container_id"]
        
        try:
            # Check if container still exists
            docker.inspect_container(container_id)
            print(f"✓ {env['name']}: Container exists")
        except RuntimeError:
            print(f"✗ {env['name']}: Container missing")
            orphaned.append(env["name"])
    
    # Clean up orphaned state
    if orphaned:
        print(f"\nCleaning up {len(orphaned)} orphaned environments...")
        for name in orphaned:
            state_manager.remove_environment(name)
            print(f"  Removed state for: {name}")
    
    print("Cleanup complete")

def list_environment_status():
    """List all environments with status"""
    
    state_manager = StateManager(Path("~/.dev-env/state"))
    docker = DockerClient()
    
    environments = state_manager.list_environments()
    
    print(f"{'Name':<20} {'Status':<10} {'Container ID':<12} {'Created'}")
    print("-" * 60)
    
    for env in environments:
        try:
            container_info = docker.inspect_container(env["container_id"])
            status = "running" if container_info["State"]["Running"] else "stopped"
        except RuntimeError:
            status = "missing"
        
        print(f"{env['name']:<20} {status:<10} {env['container_id'][:12]:<12} {env['created_at'][:10]}")

# Usage
cleanup_environments()
list_environment_status()
```

For integration examples, see the [Integration Guide](integration.md). For extension patterns, see the [Extension Guide](extending.md).