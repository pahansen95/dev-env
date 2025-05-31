# Configuration Guide

This guide provides a complete reference for configuring development environments with dev-env.

## Configuration Basics

Dev-env uses Python files for configuration, providing type safety, validation, and dynamic composition.

### Configuration File Structure

```python
from dev_env.config import Environment, GitConfig, VolumeMount

# Single environment (most common)
environment = Environment(
    name="myproject",
    base_image="python:3.13",
    # ... additional configuration
)

# Multiple environments (advanced)
environments = {
    "frontend": Environment(...),
    "backend": Environment(...),
    "database": Environment(...)
}
```

## Environment Configuration

### Core Properties

```python
Environment(
    # Required fields
    name="unique-identifier",        # Unique name for this environment
    base_image="ubuntu:22.04",       # Docker image to use
    
    # Optional fields with defaults
    command=["/bin/bash"],           # Container entrypoint command
    working_dir="/workspace",        # Default working directory
    user="dev",                      # Container user (non-root recommended)
    hostname=None,                   # Custom hostname (defaults to name)
)
```

### Environment Variables

Set environment variables for your container:

```python
environment = Environment(
    name="webapp",
    base_image="python:3.13",
    environment={
        "DEBUG": "true",
        "DATABASE_URL": "postgresql://localhost/dev",
        "PYTHONUNBUFFERED": "1",
        "NODE_ENV": "development"
    }
)
```

**Best Practices:**
- Store secrets in `.env` files, not in configuration
- Use environment variables for configuration that changes between environments
- Set language-specific variables (PYTHONUNBUFFERED, NODE_ENV, etc.)

### Port Configuration

Map container ports to host ports for service access:

```python
environment = Environment(
    name="fullstack",
    base_image="node:20",
    ports={
        22: {"HostPort": 2222},      # SSH access (automatic setup)
        3000: {"HostPort": 3000},    # Frontend dev server
        5000: {"HostPort": 5000},    # Backend API
        5432: {"HostPort": 5432}     # PostgreSQL
    }
)
```

**Port Mapping Syntax:**
- Key: Container port
- Value: Dict with "HostPort" and optional "HostIP" (default: "127.0.0.1")

**SSH Configuration:**
- Port 22 enables automatic SSH server setup
- SSH keys from host are automatically authorized
- Non-root user with sudo access is configured

## Volume Management

### Volume Types

Dev-env supports two volume types:

#### 1. Bind Mounts
Link host directories to container paths:

```python
VolumeMount(
    source="./src",              # Relative or absolute host path
    target="/app/src",           # Container path
    mode="rw",                   # "rw" (read-write) or "ro" (read-only)
    type="bind"                  # Mount type (default)
)
```

#### 2. Named Volumes
Docker-managed persistent storage:

```python
VolumeMount(
    source="myproject-cache",    # Volume name
    target="/root/.cache",       # Container path
    mode="rw",                   # Access mode
    type="named"                 # Specify named volume
)
```

### Common Volume Patterns

```python
environment = Environment(
    name="development",
    base_image="python:3.13",
    volumes=[
        # Source code (bind mount for live editing)
        VolumeMount(source=".", target="/app"),
        
        # Package cache (named volume for persistence)
        VolumeMount(
            source="pip-cache",
            target="/root/.cache/pip",
            type="named"
        ),
        
        # Credentials (read-only bind mount)
        VolumeMount(
            source="~/.aws",
            target="/home/dev/.aws",
            mode="ro"
        ),
        
        # Database data (named volume)
        VolumeMount(
            source="postgres-data",
            target="/var/lib/postgresql/data",
            type="named"
        )
    ]
)
```

## Git Integration

### Basic Repository Setup

```python
environment = Environment(
    name="myproject",
    base_image="python:3.13",
    git=GitConfig(
        url="https://github.com/username/repo.git"
    )
)
```

### Advanced Git Configuration

```python
git=GitConfig(
    # Repository URL (HTTPS or SSH)
    url="git@github.com:organization/project.git",
    
    # Branch to checkout (default: repository default)
    branch="develop",
    
    # Clone destination (default: /workspace)
    path="/app",
    
    # Shallow clone for faster setup (default: True)
    shallow=True,
    
    # Submodules handling
    submodules=True,
    
    # Additional git config
    config={
        "user.name": "Dev User",
        "user.email": "dev@example.com"
    }
)
```

### Git Authentication

**HTTPS Repositories:**
- Use personal access tokens in URL
- Or configure git credentials in container

**SSH Repositories:**
- SSH agent forwarding is automatically configured
- Host SSH keys are available in container

## Security Settings

### User Configuration

```python
environment = Environment(
    name="secure-env",
    base_image="ubuntu:22.04",
    user="dev",                    # Non-root user
    security_opt=[
        "no-new-privileges:true",  # Prevent privilege escalation
        "seccomp=unconfined"       # For development tools
    ],
    cap_drop=["ALL"],              # Drop all capabilities
    cap_add=["SYS_PTRACE"],        # Add specific capabilities
    read_only=False                # Filesystem read-only mode
)
```

### Resource Limits

```python
environment = Environment(
    name="limited-env",
    base_image="node:20",
    # Memory limit
    memory="2g",                   # 2 gigabytes
    memory_swap="4g",              # Total memory + swap
    
    # CPU limits
    cpus=2.0,                      # Number of CPUs
    cpu_shares=1024,               # Relative CPU weight
    
    # Storage limits
    shm_size="256m",               # Shared memory size
    ulimits=[
        {"Name": "nofile", "Soft": 65536, "Hard": 65536}
    ]
)
```

## Network Configuration

### Custom Networks

```python
from dev_env.config import NetworkConfig

environment = Environment(
    name="api-service",
    base_image="python:3.13",
    network=NetworkConfig(
        name="microservices",      # Network name
        driver="bridge",           # Network driver
        ipv6=False,                # IPv6 support
        internal=False             # External connectivity
    )
)
```

### Multi-Service Networking

```python
# Shared network configuration
app_network = NetworkConfig(name="app-network")

# Frontend service
frontend = Environment(
    name="frontend",
    base_image="node:20",
    network=app_network
)

# Backend service
backend = Environment(
    name="backend",
    base_image="python:3.13",
    network=app_network
)

environments = {
    "frontend": frontend,
    "backend": backend
}
```

## Template Patterns

### Language-Specific Templates

```python
def python_env(name: str, repo: str, python_version: str = "3.13") -> Environment:
    """Template for Python projects"""
    return Environment(
        name=name,
        base_image=f"python:{python_version}",
        git=GitConfig(url=repo),
        volumes=[
            VolumeMount(source=".", target="/app"),
            VolumeMount(
                source=f"{name}-pip-cache",
                target="/root/.cache/pip",
                type="named"
            )
        ],
        environment={
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1"
        },
        ports={22: {"HostPort": 2222}}
    )

def node_env(name: str, repo: str, node_version: str = "20") -> Environment:
    """Template for Node.js projects"""
    return Environment(
        name=name,
        base_image=f"node:{node_version}",
        git=GitConfig(url=repo),
        volumes=[
            VolumeMount(source=".", target="/app"),
            VolumeMount(
                source=f"{name}-node-modules",
                target="/app/node_modules",
                type="named"
            )
        ],
        environment={
            "NODE_ENV": "development",
            "CHOKIDAR_USEPOLLING": "true"
        },
        ports={
            22: {"HostPort": 2222},
            3000: {"HostPort": 3000}
        }
    )

# Usage
environment = python_env("myapi", "git@github.com:user/api.git")
```

### Base Configuration Extension

```python
# Base configuration with common settings
base_config = {
    "volumes": [
        VolumeMount(
            source="~/.config",
            target="/home/dev/.config",
            mode="ro"
        )
    ],
    "environment": {
        "TERM": "xterm-256color",
        "TZ": "UTC"
    },
    "security_opt": ["no-new-privileges:true"]
}

# Extend base configuration
environment = Environment(
    name="extended-env",
    base_image="ubuntu:22.04",
    **base_config,  # Unpack base configuration
    ports={8080: {"HostPort": 8080}}
)
```

## Validation and Best Practices

### Configuration Validation

Dev-env validates configuration at runtime:
- Required fields must be provided
- Port numbers must be valid (1-65535)
- Volume paths must be absolute in container
- Memory/CPU limits must be positive

### Best Practices

1. **Version Control**: Store configuration files with your project
2. **Environment Separation**: Use different configs for dev/test/prod
3. **Resource Limits**: Set appropriate limits to prevent resource exhaustion
4. **Volume Strategy**: Use named volumes for persistence, bind mounts for code
5. **Security First**: Always run as non-root user, limit capabilities
6. **Port Management**: Only expose necessary ports, bind to localhost
7. **Documentation**: Comment complex configurations

### Common Pitfalls

- **Avoid hardcoding paths**: Use relative paths or Path objects
- **Don't store secrets**: Use environment files or secret management
- **Volume permissions**: Ensure container user can access mounted volumes
- **Port conflicts**: Check for existing services on host ports
- **Image tags**: Specify exact versions for reproducibility

## Advanced Examples

### Full-Stack Application

```python
from pathlib import Path
from dev_env.config import Environment, GitConfig, VolumeMount, NetworkConfig

# Shared configuration
project_network = NetworkConfig(name="fullstack-network")
project_name = "myapp"

# Frontend environment
frontend = Environment(
    name=f"{project_name}-frontend",
    base_image="node:20-alpine",
    git=GitConfig(
        url="git@github.com:org/frontend.git",
        path="/app"
    ),
    network=project_network,
    ports={
        3000: {"HostPort": 3000},
        22: {"HostPort": 2223}
    },
    volumes=[
        VolumeMount(source="./frontend", target="/app"),
        VolumeMount(
            source=f"{project_name}-node-modules",
            target="/app/node_modules",
            type="named"
        )
    ],
    environment={
        "NODE_ENV": "development",
        "REACT_APP_API_URL": "http://localhost:5000"
    }
)

# Backend environment
backend = Environment(
    name=f"{project_name}-backend",
    base_image="python:3.13-slim",
    git=GitConfig(
        url="git@github.com:org/backend.git",
        path="/app"
    ),
    network=project_network,
    ports={
        5000: {"HostPort": 5000},
        22: {"HostPort": 2224}
    },
    volumes=[
        VolumeMount(source="./backend", target="/app"),
        VolumeMount(
            source=f"{project_name}-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "FLASK_ENV": "development",
        "DATABASE_URL": "postgresql://postgres:dev@database:5432/myapp"
    }
)

# Database environment
database = Environment(
    name=f"{project_name}-database",
    base_image="postgres:16-alpine",
    network=project_network,
    ports={
        5432: {"HostPort": 5432}
    },
    volumes=[
        VolumeMount(
            source=f"{project_name}-postgres-data",
            target="/var/lib/postgresql/data",
            type="named"
        )
    ],
    environment={
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "dev",
        "POSTGRES_DB": "myapp"
    }
)

# Export all environments
environments = {
    "frontend": frontend,
    "backend": backend,
    "database": database
}
```

This configuration guide should help you create and customize development environments for any project. For specific command usage, see the [Command Reference](commands.md).