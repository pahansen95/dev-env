# dev-env

Zero-dependency development environment management for Python developers. Create isolated, reproducible development environments in seconds using only Python's standard library and Docker.

## Features

- **Zero Dependencies**: Uses only Python 3.13+ standard library
- **Instant Environments**: Create fully-configured workspaces in under 30 seconds
- **Context-Aware**: Automatic workspace detection and environment management
- **Interactive Setup**: Guided configuration wizard for new projects
- **Persistent Storage**: Named volumes preserve data across environment recreations
- **Modern Configuration**: YAML-based configuration with intelligent defaults

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

1. Navigate to your project directory:

```bash
cd /path/to/your/project
```

2. Start your development environment:

```bash
python -m dev_env work
```

The `work` command will:
- Detect or create a development context for your project
- Run an interactive setup wizard if no configuration exists  
- Create and start your development environment
- Display connection instructions

3. Enter your development environment:

```bash
python -m dev_env shell
```

4. Execute commands in your environment:

```bash
python -m dev_env run python --version
python -m dev_env run pip install -r requirements.txt
```

## Core Commands

### User Commands
- `work` - Start or resume development session  
- `stop` - Stop development environment
- `status` - Show environment status (use `--all` for all environments)
- `shell` - Open interactive shell in environment
- `run` - Execute command in environment

### Context Management
- `context-create` - Create new development context
- `context-resolve` - Resolve context from current directory
- `context-list` - List all development contexts

### Environment Control
- `env-create` - Create environment from configuration
- `env-start` - Start existing environment  
- `env-stop` - Stop running environment
- `env-status` - Get detailed environment status

## Configuration

Dev-env uses YAML configuration files (`dev-env.yaml`) that are automatically created through an interactive setup wizard:

### Python Development

```yaml
# Development Environment Configuration
base_image: python:3.13
ports:
  - container: 8000
    host: 8000
volumes:
  - source: .
    target: /workspace
  - source: pip-cache
    target: /root/.cache/pip
    type: named
environment:
  PYTHONPATH: /workspace
working_directory: /workspace
```

### Node.js Development

```yaml
# Development Environment Configuration  
base_image: node:20-slim
ports:
  - container: 3000
    host: 3000
volumes:
  - source: .
    target: /app
  - source: node_modules
    target: /app/node_modules
    type: named
environment:
  NODE_ENV: development
working_directory: /app
```

### Advanced Configuration

```yaml
# Development Environment Configuration
base_image: ubuntu:22.04
ports:
  - container: 22
    host: 2222
  - container: 8080
    host: 8080
volumes:
  - source: .
    target: /workspace
  - source: docker-cache
    target: /var/lib/docker
    type: named
environment:
  DEBUG: "true"
  LOG_LEVEL: info
network:
  name: dev-network
  driver: bridge
setup_commands:
  - apt-get update && apt-get install -y curl
  - curl -fsSL https://get.docker.com | sh
working_directory: /workspace
```

## Documentation

- [User Guide](docs/user-guide.md) - Complete usage documentation with workflows and configuration
- [Design](docs/design.md) - Architecture, vision, and implementation details
- [Migration Guide](#migration-from-legacy-commands) - Upgrading from previous versions

## Context-Based Workflow

Dev-env automatically manages development contexts based on your project structure:

1. **Context Detection**: Automatically detects existing contexts in your directory tree
2. **Configuration Discovery**: Finds and validates `dev-env.yaml` configuration files
3. **Environment Lifecycle**: Manages container creation, startup, and cleanup
4. **Resource Persistence**: Preserves volumes, networks, and state across sessions

### Typical Workflow

```bash
# Start working on a project
cd my-project
dev-env work                    # Creates context and environment

# Work in your environment  
dev-env shell                   # Interactive development
dev-env run pytest             # Run tests
dev-env run python app.py      # Start application

# Check status
dev-env status                  # Current environment
dev-env status --all           # All environments

# Stop when done
dev-env stop                    # Stop current environment
```

## Migration from Legacy Commands

If you're upgrading from a previous version, here's the command mapping:

| Legacy Command | New Command | Notes |
|----------------|-------------|-------|
| `dev-env up config.py` | `dev-env work` | Auto-detects context, uses YAML config |
| `dev-env down name` | `dev-env stop` | Context-aware, stops current environment |
| `dev-env list` | `dev-env status --all` | Rich formatting with timestamps |
| `dev-env exec name cmd` | `dev-env run cmd` | Auto-resolves context |
| `dev-env ssh name` | `dev-env shell` | Context-aware shell access |
| `dev-env logs name` | Integrated into `dev-env status` | View logs through status command |

### Configuration Migration

Legacy Python configuration files need to be converted to YAML format:

**Legacy (`config.py`):**
```python
from dev_env.config import Environment

environment = Environment(
    name="myproject",
    base_image="python:3.13",
    ports={8000: {"HostPort": 8000}}
)
```

**Modern (`dev-env.yaml`):**
```yaml
base_image: python:3.13
ports:
  - container: 8000
    host: 8000
```

Run `dev-env work` in your project directory to automatically generate modern configuration through the setup wizard.

## Why dev-env?

Traditional development environment tools require complex dependency chains, slow VM provisioning, or cloud infrastructure. Dev-env provides the benefits of containerized development using only Python's standard library:

- **No dependency hell** - Zero external packages required
- **Fast startup** - Environments start in seconds, not minutes  
- **Local-first** - Everything runs on your machine
- **Context-aware** - Automatically detects and manages project environments
- **Persistent state** - Your work survives container restarts

## Architecture

Dev-env implements a minimal Docker client using Python's `http.client` to communicate directly with the Docker daemon via Unix socket. The context-based architecture provides automatic workspace detection and lifecycle management. Configuration uses YAML for human readability while maintaining validation through Python dataclasses. State persistence leverages `sqlite3` for reliable environment and context tracking.

## Contributing

Contributions welcome! The project maintains zero runtime dependencies - any code must use only Python 3.13+ standard library modules.

## License

MIT License - see LICENSE file for details