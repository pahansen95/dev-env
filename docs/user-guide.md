# Dev-Env User Documentation

## Quick Start Guide

Dev-Env provides rapidly deployable, isolated development environments using Docker containers. This guide covers installation, basic usage, and common workflows.

### Prerequisites

- Python 3.13 or higher
- Docker installed and running
- Unix-like operating system (Linux, macOS, WSL2)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/dev-env.git
cd dev-env

# Install in development mode
pip install -e .

# Or run directly without installation
python -m dev_env --help
```

### Your First Environment

1. **Create a configuration file** (`myproject.py`):

```python
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="myproject",
    base_image="python:3.13-slim",
    command=["/bin/bash"],
    ports={
        22: {"HostPort": 2222},    # SSH access
        8000: {"HostPort": 8000}   # Application port
    },
    git=GitConfig(
        url="https://github.com/yourusername/myproject.git",
        branch="main"
    )
)
```

2. **Start the environment**:

```bash
python -m dev_env up myproject.py
```

3. **Connect via SSH**:

```bash
python -m dev_env ssh myproject
```

4. **Execute commands**:

```bash
python -m dev_env exec myproject python --version
```

5. **Stop and remove**:

```bash
python -m dev_env down myproject
```

## Configuration Reference

### Environment Configuration

The `Environment` dataclass defines your development workspace:

```python
Environment(
    name="unique-identifier",              # Required: Environment name
    base_image="ubuntu:22.04",            # Required: Docker image
    command=["/bin/bash"],                # Optional: Container command
    environment={                         # Optional: Environment variables
        "KEY": "value"
    },
    volumes=[                             # Optional: Volume mounts
        VolumeMount(
            source=".",                   # Host path or volume name
            target="/workspace",          # Container path
            mode="rw",                    # Access mode: "rw" or "ro"
            type="bind"                   # Mount type: "bind" or "named"
        )
    ],
    ports={                               # Optional: Port mappings
        22: {"HostPort": 2222},          # SSH port (enables SSH access)
        8080: {"HostPort": 8080}         # Application ports
    },
    git=GitConfig(                        # Optional: Git repository
        url="https://github.com/...",
        branch="main",
        path="/workspace",
        shallow=True                      # Shallow clone for speed
    ),
    network=NetworkConfig(                # Optional: Custom network
        name="mynetwork",
        driver="bridge"
    )
)
```

### Volume Management

Dev-Env supports two volume types:

**Bind Mounts** - Link host directories:
```python
VolumeMount(
    source="./src",           # Relative or absolute host path
    target="/app/src",        # Container path
    mode="rw"                 # Read-write access
)
```

**Named Volumes** - Persistent Docker volumes:
```python
VolumeMount(
    source="myproject-cache",  # Volume name
    target="/root/.cache",     # Container path
    type="named"               # Specify named volume
)
```

## Common Workflows

### Python Web Development

```python
# django-dev.py
from dev_env.config import Environment, VolumeMount, GitConfig

environment = Environment(
    name="django-app",
    base_image="python:3.13",
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}  # Django dev server
    },
    environment={
        "PYTHONUNBUFFERED": "1",
        "DJANGO_SETTINGS_MODULE": "myproject.settings.dev"
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="django-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    git=GitConfig(
        url="git@github.com:yourusername/django-app.git",
        path="/app"
    )
)
```

Usage:
```bash
# Start environment
python -m dev_env up django-dev.py

# SSH in and run Django
python -m dev_env ssh django-app
cd /app
pip install -r requirements.txt
python manage.py runserver 0.0.0.0:8000

# Access at http://localhost:8000
```

### Node.js Full Stack

```python
# node-fullstack.py
from dev_env.config import Environment, VolumeMount, NetworkConfig

environment = Environment(
    name="node-app",
    base_image="node:20",
    ports={
        22: {"HostPort": 2223},
        3000: {"HostPort": 3000},  # Frontend
        5000: {"HostPort": 5000}   # Backend API
    },
    environment={
        "NODE_ENV": "development",
        "CHOKIDAR_USEPOLLING": "true"  # Hot reload in Docker
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="node-modules",
            target="/app/node_modules",
            type="named"
        )
    ],
    network=NetworkConfig(name="fullstack-net")
)
```

### Database Development

```python
# postgres-dev.py
from dev_env.config import Environment, VolumeMount

environment = Environment(
    name="postgres-dev",
    base_image="postgres:16",
    ports={
        5432: {"HostPort": 5432}
    },
    environment={
        "POSTGRES_USER": "devuser",
        "POSTGRES_PASSWORD": "devpass",
        "POSTGRES_DB": "devdb"
    },
    volumes=[
        VolumeMount(
            source="postgres-data",
            target="/var/lib/postgresql/data",
            type="named"
        ),
        VolumeMount(
            source="./init-scripts",
            target="/docker-entrypoint-initdb.d",
            mode="ro"
        )
    ]
)
```

## Command Reference

### Core Commands

**`up`** - Create and start an environment
```bash
python -m dev_env up <config-file> [--name <override-name>]
```

**`down`** - Stop and remove an environment
```bash
python -m dev_env down <env-name> [--volumes]  # --volumes removes data
```

**`list`** - Show all environments
```bash
python -m dev_env list
```

**`exec`** - Run commands in environment
```bash
python -m dev_env exec <env-name> <command> [args...]
```

**`ssh`** - SSH into environment
```bash
python -m dev_env ssh <env-name> [ssh-options]
```

**`logs`** - View container logs
```bash
python -m dev_env logs <env-name> [-f] [--tail 50]
```

**`attach`** - Attach to container's main process
```bash
python -m dev_env attach <env-name>
```

### Global Options

- `--state-dir <path>` - Override state directory (default: `~/.dev-env/state`)
- `--version` - Show version information

## Troubleshooting

### Docker Connection Issues

**Error**: "Docker daemon is not accessible"

**Solution**:
```bash
# Linux: Start Docker service
sudo systemctl start docker

# macOS: Start Docker Desktop

# Add user to docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in
```

### Port Conflicts

**Error**: "Port 8000 is already in use"

**Solution**:
1. Find process using port: `lsof -i :8000`
2. Stop conflicting process or use different port
3. Update port mapping in configuration

### SSH Connection Failed

**Error**: "SSH server not responding"

**Symptoms**: Container running but SSH fails

**Solution**:
```bash
# Check container logs
python -m dev_env logs <env-name> --tail 100

# Verify SSH is enabled (port 22 in config)
# Ensure base image supports package installation
```

### Volume Mount Issues

**Error**: "Bind mount source does not exist"

**Solution**:
1. Create missing directories before starting
2. Use absolute paths for clarity
3. Check file permissions

## Best Practices

### Configuration Management

1. **Version control your configs**: Store environment configurations alongside project code
2. **Use templates**: Create reusable base configurations for common stacks
3. **Environment variables**: Store secrets in `.env` files, not in configs

### Resource Optimization

1. **Named volumes for caches**: Persist package caches across recreations
2. **Shallow git clones**: Use `shallow=True` for faster repository setup
3. **Appropriate base images**: Use `-slim` variants when possible

### Security Considerations

1. **Avoid root passwords**: Use key-based SSH authentication only
2. **Limit port exposure**: Only expose necessary ports to localhost
3. **Regular updates**: Keep base images updated for security patches

## Advanced Usage

### Custom Networks

Create isolated networks for multi-service development:

```python
environment = Environment(
    name="api-service",
    base_image="python:3.13",
    network=NetworkConfig(
        name="microservices",
        driver="bridge"
    )
)
```

### Shell Completion

Enable tab completion for commands:

```bash
# Bash
python -m dev_env completion bash > ~/.dev-env-completion.bash
echo 'source ~/.dev-env-completion.bash' >> ~/.bashrc

# Zsh
python -m dev_env completion zsh > ~/.zsh/completions/_dev-env

# Fish
python -m dev_env completion fish > ~/.config/fish/completions/dev-env.fish
```

### State Management

Dev-Env stores environment state in SQLite:

```bash
# Default location
~/.dev-env/state/environments.db

# Clean up orphaned state
sqlite3 ~/.dev-env/state/environments.db "SELECT name FROM environments;"
```

## Migration Guide

### From Docker Compose

```yaml
# docker-compose.yml
services:
  web:
    image: python:3.13
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    environment:
      - DEBUG=true
```

Becomes:

```python
# dev-env.py
environment = Environment(
    name="web",
    base_image="python:3.13",
    ports={8000: {"HostPort": 8000}},
    volumes=[VolumeMount(source=".", target="/app")],
    environment={"DEBUG": "true"}
)
```

### From Vagrant

Key differences:
- Containers instead of VMs (faster startup)
- Docker images instead of box files
- Python configuration instead of Ruby
- No provider abstraction (Docker-only)

## Support

- **Issues**: Report bugs via GitHub issues
- **Documentation**: This guide and architecture docs
- **Examples**: See `examples/` directory for more configurations