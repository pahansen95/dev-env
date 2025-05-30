# dev-env

Zero-dependency development environment management for Python developers. Create isolated, reproducible development environments in seconds using only Python's standard library and Docker.

## Features

- **Zero Dependencies**: Uses only Python 3.13+ standard library
- **Instant Environments**: Create fully-configured workspaces in under 30 seconds
- **SSH Access**: Automatic SSH server configuration with key-based authentication
- **Git Integration**: Clone and configure repositories with host identity inheritance
- **Persistent Storage**: Named volumes preserve data across environment recreations
- **Simple Configuration**: Define environments using Python dataclasses or JSON

## Requirements

- Python 3.13 or higher
- Docker installed and running
- Unix-like OS (Linux, macOS, WSL2)

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/dev-env.git
cd dev-env

# Install package
pip install -e .

# Or run directly
python -m dev_env --help
```

## Quick Start

1. Create an environment configuration (`myproject.py`):

```python
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="myproject",
    base_image="python:3.13-slim",
    ports={22: {"HostPort": 2222}},
    git=GitConfig(
        url="https://github.com/user/repo.git",
        branch="main"
    )
)
```

2. Start the environment:

```bash
python -m dev_env up myproject.py
```

3. Connect via SSH:

```bash
python -m dev_env ssh myproject
```

## Core Commands

- `up` - Create and start an environment
- `down` - Stop and remove an environment  
- `list` - Show all environments
- `exec` - Execute commands in environment
- `ssh` - SSH into environment
- `logs` - View container logs
- `attach` - Attach to container process

## Example Configurations

### Python Development

```python
from dev_env.config import Environment, VolumeMount

environment = Environment(
    name="python-dev",
    base_image="python:3.13",
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source=".", target="/workspace"),
        VolumeMount(
            source="pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ]
)
```

### Node.js Development

```python
environment = Environment(
    name="node-dev",
    base_image="node:20-slim",
    ports={
        22: {"HostPort": 2223},
        3000: {"HostPort": 3000}
    },
    environment={"NODE_ENV": "development"},
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="node_modules",
            target="/app/node_modules",
            type="named"
        )
    ]
)
```

## Documentation

- [User Guide](docs/user-guide.md) - Complete usage documentation with quick start, workflows, and configuration
- [Design](docs/design.md) - Architecture, vision, and implementation details
- [Examples](examples/) - Ready-to-use environment configurations for Python, Node.js, and more

## Why dev-env?

Traditional development environment tools require complex dependency chains, slow VM provisioning, or cloud infrastructure. Dev-env provides the benefits of containerized development using only Python's standard library:

- **No dependency hell** - Zero external packages required
- **Fast startup** - Containers start in seconds, not minutes
- **Local-first** - Everything runs on your machine
- **Git-native** - Automatic repository setup with your SSH keys
- **Persistent state** - Your work survives container restarts

## Architecture

Dev-env implements a minimal Docker client using Python's `http.client` to communicate directly with the Docker daemon via Unix socket. Configuration uses Python's `dataclasses` for type safety and validation. State persistence leverages `sqlite3` for reliable environment tracking.

## Contributing

Contributions welcome! The project maintains zero runtime dependencies - any code must use only Python 3.13+ standard library modules.

## License

MIT License - see LICENSE file for details