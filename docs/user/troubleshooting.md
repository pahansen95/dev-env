# Troubleshooting Guide

This guide helps resolve common issues when using dev-env.

## Quick Diagnostics

Before diving into specific issues, run these diagnostic commands:

```bash
# Check Docker status
docker version
docker ps

# Check dev-env installation
dev-env --version

# List environments
dev-env list

# Check specific environment logs
dev-env logs <env-name> --tail 50
```

## Docker Connection Issues

### "Docker daemon is not accessible"

**Symptoms:**
```
Error: Docker daemon is not accessible
Please ensure Docker is installed and running
```

**Solutions:**

1. **Linux**: Start Docker service
   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker  # Auto-start on boot
   ```

2. **macOS**: Start Docker Desktop
   - Open Docker Desktop from Applications
   - Wait for "Docker Desktop is running" in menu bar

3. **Windows (WSL2)**: Ensure Docker Desktop is running
   - Start Docker Desktop
   - Check Settings → Resources → WSL Integration
   - Enable integration for your distro

4. **Permission issues (Linux)**:
   ```bash
   # Add user to docker group
   sudo usermod -aG docker $USER
   
   # Log out and back in, then verify
   groups | grep docker
   ```

### "Cannot connect to Docker daemon at unix:///var/run/docker.sock"

**Cause**: Docker socket not accessible

**Solutions:**
```bash
# Check socket exists
ls -la /var/run/docker.sock

# Check Docker service
sudo systemctl status docker

# Reset Docker (last resort)
sudo systemctl restart docker
```

## Port Conflicts

### "Port already in use"

**Symptoms:**
```
Error creating container: port 8000 is already in use
```

**Solutions:**

1. **Find process using port**:
   ```bash
   # Linux/macOS
   lsof -i :8000
   
   # Alternative
   netstat -tlnp | grep 8000
   ```

2. **Stop conflicting process**:
   ```bash
   # Using PID from above
   kill <PID>
   
   # Or stop service
   sudo systemctl stop <service-name>
   ```

3. **Use different port**:
   ```python
   # In configuration
   ports={
       8000: {"HostPort": 8001}  # Changed to 8001
   }
   ```

### Multiple services on same port

**Issue**: Running multiple environments with same port mapping

**Solution**: Use port offsets
```python
# config.py
def create_env(name: str, port_offset: int):
    return Environment(
        name=name,
        base_image="python:3.13",
        ports={
            22: {"HostPort": 2222 + port_offset},
            8000: {"HostPort": 8000 + port_offset}
        }
    )
```

## SSH Connection Problems

### "SSH connection refused"

**Symptoms:**
```
ssh: connect to host localhost port 2222: Connection refused
```

**Causes & Solutions:**

1. **SSH not enabled**: Ensure port 22 is mapped
   ```python
   ports={
       22: {"HostPort": 2222}  # Required for SSH
   }
   ```

2. **Container not running**:
   ```bash
   # Check status
   dev-env list
   
   # Start if needed
   dev-env up <config-file>
   ```

3. **SSH server failed to start**:
   ```bash
   # Check container logs
   dev-env logs <env-name> | grep ssh
   
   # Manually check inside container
   docker exec <container-id> service ssh status
   ```

### "Permission denied (publickey)"

**Cause**: SSH key not authorized

**Solutions:**

1. **Check SSH agent**:
   ```bash
   # List loaded keys
   ssh-add -l
   
   # Add default key
   ssh-add ~/.ssh/id_rsa
   ```

2. **Verify key in container**:
   ```bash
   # Check authorized keys
   docker exec <container-id> cat /home/dev/.ssh/authorized_keys
   ```

3. **Use password authentication** (not recommended):
   ```bash
   # Connect without key
   ssh -o PreferredAuthentications=password user@localhost -p 2222
   ```

## Volume Mount Errors

### "Bind mount source path does not exist"

**Symptoms:**
```
Error creating container: bind mount source ./data does not exist
```

**Solutions:**

1. **Create missing directory**:
   ```bash
   mkdir -p ./data
   ```

2. **Use absolute paths**:
   ```python
   from pathlib import Path
   
   VolumeMount(
       source=Path.cwd() / "data",  # Absolute path
       target="/app/data"
   )
   ```

3. **Check working directory**:
   ```bash
   # Ensure you're in the right directory
   pwd
   ls -la
   ```

### "Permission denied" in mounted volumes

**Symptoms:**
- Cannot write to mounted directories
- Files created as root

**Solutions:**

1. **Set proper ownership** (Linux):
   ```bash
   # Match container user ID (usually 1000)
   sudo chown -R 1000:1000 ./data
   ```

2. **Use named volumes** for better permissions:
   ```python
   VolumeMount(
       source="app-data",
       target="/app/data",
       type="named"
   )
   ```

3. **Configure user in container**:
   ```python
   environment = Environment(
       name="app",
       base_image="ubuntu:22.04",
       user="1000:1000"  # Match host user
   )
   ```

## Git Clone Failures

### "Repository not found" or "Authentication failed"

**Symptoms:**
```
Error during container initialization: Failed to clone repository
```

**Solutions:**

1. **HTTPS repositories** - Use personal access token:
   ```python
   git=GitConfig(
       url="https://username:token@github.com/org/repo.git"
   )
   ```

2. **SSH repositories** - Check SSH agent:
   ```bash
   # Start SSH agent
   eval "$(ssh-agent -s)"
   
   # Add key
   ssh-add ~/.ssh/id_rsa
   
   # Test GitHub connection
   ssh -T git@github.com
   ```

3. **Private repositories** - Configure git credentials:
   ```python
   environment = Environment(
       name="private-app",
       base_image="python:3.13",
       volumes=[
           VolumeMount(
               source="~/.ssh",
               target="/root/.ssh",
               mode="ro"
           )
       ]
   )
   ```

### "SSL certificate problem"

**Cause**: Corporate proxy or self-signed certificates

**Solutions:**

1. **Disable SSL verification** (development only):
   ```python
   git=GitConfig(
       url="https://github.com/org/repo.git",
       config={
           "http.sslVerify": "false"
       }
   )
   ```

2. **Add CA certificates**:
   ```python
   volumes=[
       VolumeMount(
           source="/etc/ssl/certs",
           target="/etc/ssl/certs",
           mode="ro"
       )
   ]
   ```

## Performance Issues

### Slow container startup

**Symptoms:**
- Takes minutes to create environment
- Hangs during image pull

**Solutions:**

1. **Use local images**:
   ```bash
   # Pre-pull images
   docker pull python:3.13-slim
   ```

2. **Enable shallow clones**:
   ```python
   git=GitConfig(
       url="https://github.com/large/repo.git",
       shallow=True  # Only recent history
   )
   ```

3. **Optimize Dockerfile** (if using custom images):
   ```dockerfile
   # Use specific versions
   FROM python:3.13-slim
   
   # Cache dependencies
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   
   # Then copy code
   COPY . .
   ```

### High memory/CPU usage

**Symptoms:**
- System becomes unresponsive
- Container using all resources

**Solutions:**

1. **Set resource limits**:
   ```python
   environment = Environment(
       name="limited-app",
       base_image="node:20",
       memory="2g",      # Limit memory
       cpus=2.0,         # Limit CPU cores
       memory_swap="2g"  # Prevent swap usage
   )
   ```

2. **Monitor resource usage**:
   ```bash
   # Real-time stats
   docker stats <container-name>
   
   # Check limits
   docker inspect <container-name> | grep -E "(Memory|Cpu)"
   ```

## State Management Issues

### "Environment already exists"

**Symptoms:**
```
Error: Environment 'myapp' already exists
```

**Solutions:**

1. **Check existing environments**:
   ```bash
   dev-env list
   ```

2. **Remove old environment**:
   ```bash
   dev-env down myapp
   ```

3. **Force recreate**:
   ```bash
   # Remove completely
   dev-env down myapp --volumes
   
   # Then create fresh
   dev-env up config.py
   ```

### Orphaned containers

**Symptoms:**
- Containers exist but not shown in `dev-env list`
- Cannot create environment due to name conflict

**Solutions:**

1. **Clean up manually**:
   ```bash
   # List all containers
   docker ps -a | grep dev-
   
   # Remove orphaned containers
   docker rm <container-id>
   
   # Remove orphaned volumes
   docker volume ls | grep dev-
   docker volume rm <volume-name>
   ```

2. **Reset state database**:
   ```bash
   # Backup first
   cp ~/.dev-env/state/environments.db ~/.dev-env/state/environments.db.bak
   
   # Reset (will lose state tracking)
   rm ~/.dev-env/state/environments.db
   ```

## Security Warnings

### "Running as root is not recommended"

**Solution**: Configure non-root user
```python
environment = Environment(
    name="secure-app",
    base_image="ubuntu:22.04",
    user="1000:1000",  # Non-root user
    # Or use username
    user="dev"
)
```

### "Capability security warnings"

**Solution**: Drop unnecessary capabilities
```python
environment = Environment(
    name="restricted-app",
    base_image="python:3.13",
    cap_drop=["ALL"],
    cap_add=["NET_BIND_SERVICE"],  # Only what's needed
    security_opt=["no-new-privileges:true"]
)
```

## Common Error Messages

### Error Reference Table

| Error | Cause | Solution |
|-------|-------|----------|
| "No such image" | Image not pulled | Run `docker pull <image>` |
| "Container name taken" | Name conflict | Use `--name` flag to override |
| "Invalid port syntax" | Wrong port format | Use dict: `{8000: {"HostPort": 8000}}` |
| "Volume mount failed" | Path doesn't exist | Create directory or use absolute path |
| "Exec format error" | Architecture mismatch | Use platform-specific image |
| "No space left" | Disk full | Run `docker system prune` |

## Getting Help

### Debugging Steps

1. **Enable verbose output** (if available):
   ```bash
   DEV_ENV_DEBUG=1 dev-env up config.py
   ```

2. **Inspect container directly**:
   ```bash
   # Get container ID
   docker ps -a | grep <env-name>
   
   # Inspect full details
   docker inspect <container-id>
   
   # Check logs
   docker logs <container-id>
   ```

3. **Test minimal configuration**:
   ```python
   # minimal.py
   from dev_env.config import Environment
   
   environment = Environment(
       name="test",
       base_image="alpine:latest",
       command=["sh", "-c", "echo 'Working!' && sleep 3600"]
   )
   ```

### Reporting Issues

When reporting issues, include:

1. **Environment details**:
   ```bash
   dev-env --version
   docker version
   uname -a  # OS info
   ```

2. **Configuration file** (sanitized)

3. **Full error output**

4. **Steps to reproduce**

For more help, see:
- [Configuration Guide](configuration.md) for setup details
- [Command Reference](commands.md) for usage information
- Project issue tracker for bug reports