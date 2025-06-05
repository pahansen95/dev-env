# Dev-Env User Documentation

## Quick Start Guide

Dev-Env provides context-aware development environment management using Docker containers. This guide covers installation, basic usage, and common workflows.

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

1. **Navigate to your project directory**:

```bash
cd /path/to/your/project
```

2. **Start your development environment**:

```bash
python -m dev_env work
```

The system will:
- Detect existing context or prompt to create one
- Launch setup wizard if no configuration exists
- Create and start your development environment
- Display connection instructions

3. **Enter your environment**:

```bash
python -m dev_env shell
```

4. **Execute commands in your environment**:

```bash
python -m dev_env run python --version
python -m dev_env run pip install -r requirements.txt
```

5. **Stop your environment**:

```bash
python -m dev_env stop
```

## Configuration Reference

### YAML Configuration Format

Dev-env uses `dev-env.yaml` files for environment configuration:

```yaml
# Development Environment Configuration
base_image: python:3.13-slim
ports:
  - container: 22
    host: 2222
  - container: 8000
    host: 8000
volumes:
  - source: .
    target: /workspace
  - source: pip-cache
    target: /root/.cache/pip
    type: named
environment:
  PYTHONUNBUFFERED: "1"
  DEBUG: "true"
working_directory: /workspace
```

### Configuration Fields

**Required Fields:**
- `base_image`: Docker image for the container

**Optional Fields:**
- `ports`: Port mappings between container and host
- `volumes`: Volume mounts for data persistence
- `environment`: Environment variables
- `working_directory`: Default working directory
- `network`: Custom network configuration
- `setup_commands`: Commands to run during container setup

### Volume Configuration

**Bind Mounts** - Link host directories:
```yaml
volumes:
  - source: ./src
    target: /app/src
    mode: rw
```

**Named Volumes** - Persistent Docker volumes:
```yaml
volumes:
  - source: myproject-cache
    target: /root/.cache
    type: named
```

**Volume Options:**
- `source`: Host path (bind) or volume name (named)
- `target`: Container mount path
- `mode`: Access mode (`rw` or `ro`)
- `type`: Mount type (`bind` or `named`)

### Port Configuration

```yaml
ports:
  - container: 8000    # Container port
    host: 8000         # Host port
  - container: 22      # SSH access
    host: 2222
```

### Network Configuration

```yaml
network:
  name: dev-network
  driver: bridge
  options:
    com.docker.network.bridge.name: dev-br0
```

## Context Management

### Context Lifecycle

Dev-env manages development contexts that represent isolated workspaces:

1. **Context Detection**: Automatically finds contexts by walking up directory tree
2. **Context Creation**: Creates new contexts when none exist
3. **Environment Association**: Links contexts to Docker containers
4. **State Persistence**: Maintains context and environment state

### Context Commands

**Create Context**:
```bash
python -m dev_env context-create myproject --path /path/to/project
```

**Resolve Context**:
```bash
python -m dev_env context-resolve --name myproject
```

**List Contexts**:
```bash
python -m dev_env context-list
```

## Common Workflows

### Python Web Development

Configuration (`dev-env.yaml`):
```yaml
base_image: python:3.13
ports:
  - container: 22
    host: 2222
  - container: 8000
    host: 8000
volumes:
  - source: .
    target: /app
  - source: pip-cache
    target: /root/.cache/pip
    type: named
environment:
  PYTHONUNBUFFERED: "1"
  DJANGO_SETTINGS_MODULE: myproject.settings.dev
working_directory: /app
setup_commands:
  - pip install --upgrade pip
  - pip install -r requirements.txt
```

Workflow:
```bash
# Start development environment
python -m dev_env work

# Access shell
python -m dev_env shell

# Run Django development server
python -m dev_env run python manage.py runserver 0.0.0.0:8000

# Access at http://localhost:8000
```

### Node.js Development

Configuration (`dev-env.yaml`):
```yaml
base_image: node:20-slim
ports:
  - container: 3000
    host: 3000
  - container: 5000
    host: 5000
volumes:
  - source: .
    target: /app
  - source: node-modules
    target: /app/node_modules
    type: named
environment:
  NODE_ENV: development
  CHOKIDAR_USEPOLLING: "true"
working_directory: /app
setup_commands:
  - npm install
```

Workflow:
```bash
# Start environment
python -m dev_env work

# Run development server
python -m dev_env run npm run dev

# Run tests
python -m dev_env run npm test
```

### Multi-Service Development

Configuration (`dev-env.yaml`):
```yaml
base_image: ubuntu:22.04
ports:
  - container: 22
    host: 2222
  - container: 3000
    host: 3000
  - container: 5432
    host: 5432
volumes:
  - source: .
    target: /workspace
  - source: postgres-data
    target: /var/lib/postgresql/data
    type: named
environment:
  POSTGRES_USER: devuser
  POSTGRES_PASSWORD: devpass
  POSTGRES_DB: devdb
network:
  name: microservices
  driver: bridge
setup_commands:
  - apt-get update
  - apt-get install -y curl postgresql-client nodejs npm
working_directory: /workspace
```

## Command Reference

### User Commands

**`work`** - Start or resume development session
```bash
python -m dev_env work [--name <context-name>]
```

**`stop`** - Stop development environment
```bash
python -m dev_env stop [--name <context-name>]
```

**`status`** - Show environment status
```bash
python -m dev_env status [--all]
```

**`shell`** - Open interactive shell
```bash
python -m dev_env shell
```

**`run`** - Execute command in environment
```bash
python -m dev_env run <command> [args...]
```

### Context Commands

**`context-create`** - Create new context
```bash
python -m dev_env context-create <name> [--path <path>]
```

**`context-resolve`** - Resolve context
```bash
python -m dev_env context-resolve [--name <name>]
```

**`context-list`** - List contexts
```bash
python -m dev_env context-list
```

### Environment Commands

**`env-create`** - Create environment
```bash
python -m dev_env env-create [--context <context>]
```

**`env-start`** - Start environment
```bash
python -m dev_env env-start [--context <context>]
```

**`env-stop`** - Stop environment
```bash
python -m dev_env env-stop [--context <context>]
```

**`env-status`** - Environment status
```bash
python -m dev_env env-status [--context <context>]
```

### Global Options

- `--state-dir <path>` - Override state directory
- `--version` - Show version information

## Setup Wizard

The interactive setup wizard guides configuration creation:

### Wizard Flow

1. **Project Type Detection**: Analyzes project structure
2. **Base Image Selection**: Recommends appropriate Docker images
3. **Port Configuration**: Configures necessary port mappings
4. **Volume Setup**: Configures workspace and cache volumes
5. **Environment Variables**: Sets up development environment
6. **Configuration Generation**: Creates `dev-env.yaml` file

### Supported Project Types

- **Python**: Django, Flask, FastAPI, general Python projects
- **Node.js**: React, Vue, Angular, Express, Next.js
- **Go**: Web services, CLI applications
- **Rust**: Web applications, system tools
- **PHP**: Laravel, Symfony, WordPress
- **Generic**: Custom configuration for any project type

## Troubleshooting

### Context Resolution Issues

**Problem**: "No context found in current directory"

**Solution**:
```bash
# Create context for current directory
python -m dev_env context-create myproject

# Or specify path explicitly
python -m dev_env work --name myproject
```

### Configuration Errors

**Problem**: "Invalid configuration file"

**Solution**:
1. Validate YAML syntax
2. Check required fields are present
3. Verify volume source paths exist
4. Ensure port numbers are available

**Common Configuration Issues**:
- Missing `base_image` field
- Invalid YAML syntax (indentation, quotes)
- Non-existent volume source paths
- Port conflicts with running services

### Docker Connection Issues

**Problem**: "Docker daemon not accessible"

**Solution**:
```bash
# Linux: Start Docker service
sudo systemctl start docker

# macOS: Start Docker Desktop

# Verify Docker access
docker info
```

### Environment Startup Failures

**Problem**: Environment fails to start

**Debugging Steps**:
```bash
# Check environment status
python -m dev_env env-status

# View container logs (if available)
docker logs <container-name>

# Recreate environment
python -m dev_env env-stop
python -m dev_env work
```

### Port Conflicts

**Problem**: "Port already in use"

**Solution**:
1. Identify conflicting process: `lsof -i :<port>`
2. Stop conflicting service or modify configuration
3. Update port mapping in `dev-env.yaml`

## Best Practices

### Project Organization

1. **Configuration Versioning**: Store `dev-env.yaml` in version control
2. **Context Naming**: Use descriptive, project-specific context names
3. **Documentation**: Document environment setup in project README

### Performance Optimization

1. **Named Volumes**: Use named volumes for package caches
2. **Layer Caching**: Choose efficient base images
3. **Resource Limits**: Consider container resource constraints

### Security Considerations

1. **Port Exposure**: Bind ports to localhost only
2. **Volume Permissions**: Use appropriate file permissions
3. **Secret Management**: Avoid hardcoding secrets in configuration

## Advanced Usage

### Custom Networks

Create isolated networks for multi-service architectures:

```yaml
network:
  name: microservices-net
  driver: bridge
  options:
    com.docker.network.bridge.enable_icc: "true"
```

### Environment Inheritance

Base configurations can be extended for different environments:

```yaml
# Base configuration
base_image: python:3.13
volumes:
  - source: .
    target: /app
working_directory: /app

# Development-specific additions
environment:
  DEBUG: "true"
  LOG_LEVEL: debug
```

### Shell Completion

Enable command completion:

```bash
# Bash
python -m dev_env completion bash > ~/.dev-env-completion.bash
echo 'source ~/.dev-env-completion.bash' >> ~/.bashrc

# Zsh  
python -m dev_env completion zsh > ~/.oh-my-zsh/completions/_dev-env

# Fish
python -m dev_env completion fish > ~/.config/fish/completions/dev-env.fish
```

## Migration Guide

### From Legacy Commands

Legacy command migration mapping:

| Legacy | Modern | Context-Aware |
|--------|---------|---------------|
| `up config.py` | `work` | Auto-detects context |
| `down name` | `stop` | Uses current context |
| `list` | `status --all` | Rich formatting |
| `exec name cmd` | `run cmd` | Context resolution |
| `ssh name` | `shell` | Interactive access |

### Configuration Migration

**Legacy Python Configuration**:
```python
Environment(
    name="myproject",
    base_image="python:3.13",
    ports={8000: {"HostPort": 8000}}
)
```

**Modern YAML Configuration**:
```yaml
base_image: python:3.13
ports:
  - container: 8000
    host: 8000
```

### Migration Process

1. **Context Creation**: Create context for existing project
2. **Configuration Conversion**: Convert Python configs to YAML
3. **Workflow Update**: Adopt context-based commands
4. **Validation**: Test new workflow thoroughly

## Support

- **Issues**: Report bugs via GitHub issues
- **Documentation**: Architecture and design documentation
- **Examples**: Configuration examples in project repository