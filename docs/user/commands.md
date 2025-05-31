# Command Reference

This guide provides detailed documentation for all dev-env commands.

## Command Overview

```bash
dev-env [global-options] <command> [command-options] [arguments]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `up` | Create and start a new environment |
| `down` | Stop and remove an environment |
| `list` | List all environments |
| `exec` | Execute a command in an environment |
| `ssh` | SSH into an environment |
| `logs` | View container logs |
| `completion` | Generate shell completion scripts |

### Global Options

- `--version` - Show version information
- `--state-dir <path>` - Override state directory (default: `~/.dev-env/state`)

## Core Commands

### `up` - Create and Start Environment

Creates a new development environment from a configuration file.

```bash
dev-env up <config-file> [options]
```

**Arguments:**
- `<config-file>` - Path to Python configuration file

**Options:**
- `--name <name>` - Override the environment name from config

**Examples:**
```bash
# Create environment using config
dev-env up myproject.py

# Create with custom name
dev-env up shared-config.py --name feature-branch
```

**What it does:**
1. Loads and validates configuration
2. Checks for port conflicts and mount issues
3. Pulls the Docker image (if needed)
4. Creates persistent volumes
5. Sets up the container
6. Configures SSH access (if port 22 is mapped)
7. Clones the git repository (if configured)
8. Starts the container

**Common Issues:**
- Port already in use: Change port mapping or stop conflicting service
- Image pull fails: Check internet connection or use local image
- Git clone fails: Verify repository URL and authentication

### `down` - Stop and Remove Environment

Stops a running environment and optionally removes its data.

```bash
dev-env down <name> [options]
```

**Arguments:**
- `<name>` - Environment name to stop

**Options:**
- `--volumes` - Also remove persistent volumes (data loss!)

**Examples:**
```bash
# Stop environment, keep data
dev-env down myproject

# Stop and remove all data
dev-env down myproject --volumes
```

**What it does:**
1. Stops the running container gracefully
2. Removes the container
3. Optionally removes associated volumes
4. Cleans up state tracking

**Warning:** Using `--volumes` will permanently delete all data in named volumes!

### `list` - List Environments

Shows all managed development environments.

```bash
dev-env list
```

**Output Format:**
```
NAME        STATUS    CONTAINER ID    IMAGE              CREATED
myproject   running   abc123def456    python:3.13        2024-01-15 10:30:00
webapp      stopped   -               node:20            2024-01-14 15:45:00
database    running   789ghi012jkl    postgres:16        2024-01-13 09:00:00
```

**Status Values:**
- `running` - Container is active
- `stopped` - Container exists but is not running
- `missing` - Container was removed externally

### `exec` - Execute Command

Runs a command inside a running environment.

```bash
dev-env exec <name> <command> [arguments...]
```

**Arguments:**
- `<name>` - Environment name
- `<command>` - Command to execute
- `[arguments...]` - Command arguments

**Examples:**
```bash
# Run Python script
dev-env exec myproject python script.py

# Install packages
dev-env exec myproject pip install -r requirements.txt

# Run tests
dev-env exec myproject pytest tests/

# Interactive Python shell
dev-env exec myproject python

# Database backup
dev-env exec database pg_dump -U postgres mydb > backup.sql
```

**Notes:**
- Commands run as the container's configured user
- Working directory is the container's WORKDIR
- Environment variables from config are available
- Exit code is preserved from the executed command

### `ssh` - SSH Access

Opens an SSH session to the environment.

```bash
dev-env ssh <name> [ssh-options]
```

**Arguments:**
- `<name>` - Environment name
- `[ssh-options]` - Additional SSH arguments

**Examples:**
```bash
# Simple SSH connection
dev-env ssh myproject

# SSH with port forwarding
dev-env ssh myproject -L 8080:localhost:8080

# SSH with X11 forwarding
dev-env ssh myproject -X

# Run single command via SSH
dev-env ssh myproject -- ls -la
```

**Requirements:**
- Environment must have port 22 mapped in configuration
- SSH server is automatically configured on container start

**SSH Features:**
- Public key authentication (no passwords)
- Agent forwarding enabled by default
- Host keys managed automatically
- Non-root user with sudo access

### `logs` - View Logs

Shows container output and logs.

```bash
dev-env logs <name> [options]
```

**Arguments:**
- `<name>` - Environment name

**Options:**
- `-f, --follow` - Follow log output (like `tail -f`)
- `--tail <n>` - Show last n lines only

**Examples:**
```bash
# Show all logs
dev-env logs myproject

# Follow logs in real-time
dev-env logs myproject -f

# Show last 50 lines
dev-env logs myproject --tail 50

# Follow logs starting from last 100 lines
dev-env logs myproject -f --tail 100
```

**Use Cases:**
- Debug startup issues
- Monitor application output
- Check service status
- Review error messages

## Shell Completion

### `completion` - Generate Completion Scripts

Generates shell completion scripts for better CLI experience.

```bash
dev-env completion <shell>
```

**Supported Shells:**
- `bash`
- `zsh`
- `fish`

**Installation:**

#### Bash
```bash
# Generate completion script
dev-env completion bash > ~/.dev-env-completion.bash

# Add to .bashrc
echo 'source ~/.dev-env-completion.bash' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

#### Zsh
```bash
# Ensure completion directory exists
mkdir -p ~/.zsh/completions

# Generate completion script
dev-env completion zsh > ~/.zsh/completions/_dev-env

# Add to .zshrc (if not already present)
echo 'fpath=(~/.zsh/completions $fpath)' >> ~/.zshrc
echo 'autoload -U compinit && compinit' >> ~/.zshrc

# Reload shell
source ~/.zshrc
```

#### Fish
```bash
# Generate completion script
dev-env completion fish > ~/.config/fish/completions/dev-env.fish

# Completions are loaded automatically
```

**Features:**
- Command name completion
- Option/flag completion
- Environment name completion for relevant commands
- File path completion for config files

## Command Patterns

### Development Workflow

```bash
# Morning startup
dev-env up project.py          # Start environment
dev-env ssh project            # Enter environment
# ... work in environment ...

# Running tests
dev-env exec project pytest    # Run tests from outside
dev-env logs project -f        # Watch test output

# End of day
dev-env down project           # Stop environment
```

### Multi-Service Management

```bash
# Start all services
dev-env up frontend.py
dev-env up backend.py
dev-env up database.py

# Check status
dev-env list

# Tail logs from all
dev-env logs frontend -f &
dev-env logs backend -f &
dev-env logs database -f &

# Stop all
dev-env down frontend
dev-env down backend  
dev-env down database
```

### Debugging Workflow

```bash
# Check if environment is running
dev-env list

# View recent logs
dev-env logs myproject --tail 100

# Execute diagnostic commands
dev-env exec myproject ps aux
dev-env exec myproject df -h
dev-env exec myproject env

# Interactive debugging
dev-env ssh myproject
```

## Exit Codes

Dev-env uses consistent exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Docker-related error |
| 4 | State management error |

## Tips and Tricks

### Command Aliases

Add to your shell configuration:

```bash
# Bash/Zsh aliases
alias de='dev-env'
alias des='dev-env ssh'
alias dex='dev-env exec'
alias del='dev-env list'

# Quick project access
alias myproject='dev-env ssh myproject'
```

### Scripting with Dev-Env

```bash
#!/bin/bash
# Script to run tests in environment

set -e  # Exit on error

ENV_NAME="myproject"

# Ensure environment is running
if ! dev-env list | grep -q "$ENV_NAME.*running"; then
    echo "Starting environment..."
    dev-env up myproject.py
fi

# Run tests
echo "Running tests..."
dev-env exec "$ENV_NAME" pytest -v

# Get test results
if [ $? -eq 0 ]; then
    echo "✅ Tests passed!"
else
    echo "❌ Tests failed!"
    exit 1
fi
```

### Checking Environment Status

```bash
# One-liner to check if environment exists and is running
dev-env list | grep -q "myproject.*running" && echo "Running" || echo "Not running"

# Function for shell profile
is_env_running() {
    dev-env list | grep -q "$1.*running"
}

# Usage
if is_env_running myproject; then
    dev-env exec myproject make test
fi
```

For more information on configuration options, see the [Configuration Guide](configuration.md).