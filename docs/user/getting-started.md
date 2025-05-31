# Getting Started with Dev-Env

This guide will get you from zero to a working development environment in 5 minutes.

## Prerequisites (30 seconds)

Before you begin, ensure you have:
- Python 3.13 or higher installed
- Docker Desktop (macOS/Windows) or Docker Engine (Linux) running
- A Unix-like terminal (Linux, macOS, or WSL2 on Windows)

Verify your setup:
```bash
python --version  # Should show 3.13 or higher
docker --version  # Should show Docker version
```

## Installation (30 seconds)

```bash
# Clone the repository
git clone https://github.com/yourusername/dev-env.git
cd dev-env

# Install dev-env
pip install -e .
```

## Your First Environment (2 minutes)

### 1. Create a Configuration File

Create `myproject.py` in your project directory:

```python
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="myproject",
    base_image="python:3.13-slim",
    git=GitConfig(
        url="https://github.com/yourusername/myproject.git"
    )
)
```

### 2. Start the Environment

```bash
dev-env up myproject.py
```

This command will:
- Pull the Python 3.13 base image
- Create a new container named "myproject"
- Clone your repository into the container
- Set up SSH access automatically

### 3. Connect to Your Environment

```bash
dev-env ssh myproject
```

You're now inside your isolated development environment with your code ready to go!

## Basic Commands (2 minutes)

### Execute Commands
Run commands without entering the container:
```bash
dev-env exec myproject python --version
dev-env exec myproject pip install -r requirements.txt
```

### View Logs
Monitor container output:
```bash
dev-env logs myproject
```

### List Environments
See all your environments:
```bash
dev-env list
```

### Stop Environment
When you're done working:
```bash
dev-env down myproject
```

## Quick Examples

### Python Web Application
```python
# webapp.py
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="webapp",
    base_image="python:3.13",
    ports={
        8000: {"HostPort": 8000}  # Access at localhost:8000
    },
    git=GitConfig(
        url="https://github.com/yourusername/webapp.git"
    )
)
```

### Node.js Project
```python
# nodeapp.py
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="nodeapp",
    base_image="node:20",
    ports={
        3000: {"HostPort": 3000}
    },
    git=GitConfig(
        url="https://github.com/yourusername/nodeapp.git"
    )
)
```

## Next Steps

Now that you have your first environment running:

1. **Explore Configuration Options**: See [Configuration Guide](configuration.md) for volumes, environment variables, and advanced settings
2. **Learn More Commands**: Check the [Command Reference](commands.md) for all available operations
3. **Common Workflows**: Read [Workflows Guide](workflows.md) for language-specific setups
4. **Troubleshooting**: If you encounter issues, see [Troubleshooting Guide](troubleshooting.md)

## Tips for Success

- **Use Named Volumes**: Persist package caches and databases between container recreations
- **Port Mapping**: Always map container ports to access web applications
- **SSH by Default**: Port 22 is automatically configured for SSH access
- **Keep It Simple**: Start with minimal configuration and add features as needed

Ready to dive deeper? Check out the [Configuration Guide](configuration.md) to customize your development environments.