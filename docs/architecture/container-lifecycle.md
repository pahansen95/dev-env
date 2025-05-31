# Container Lifecycle

This document details the complete container initialization pipeline, from environment creation to teardown.

## Lifecycle Overview

### Container States

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Created │ --> │Starting │ --> │ Running │ --> │Stopping│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │                                                 │
     └─────────────────────────────────────────────────┘
                           │
                           ▼
                      ┌─────────┐
                      │ Removed │
                      └─────────┘
```

### Lifecycle Phases

1. **Pre-Creation**: Validation and preparation
2. **Creation**: Container and resource creation
3. **Initialization**: SSH, Git, and environment setup
4. **Runtime**: Active development environment
5. **Shutdown**: Graceful termination
6. **Cleanup**: Resource deallocation

## Pre-Creation Phase

### Configuration Validation

```python
def validate_environment_config(env: Environment) -> list[str]:
    """Validate environment configuration before creation"""
    errors = []
    warnings = []
    
    # Image validation
    if not env.base_image:
        errors.append("Base image is required")
    elif ":" not in env.base_image:
        warnings.append(f"Image {env.base_image} has no tag, using 'latest'")
    
    # Port validation
    if env.ports:
        for port, config in env.ports.items():
            if port < 1 or port > 65535:
                errors.append(f"Invalid port number: {port}")
            
            host_port = config.get("HostPort", port)
            if is_port_in_use(host_port):
                warnings.append(f"Port {host_port} is already in use")
    
    # Volume validation
    if env.volumes:
        for volume in env.volumes:
            if volume.type == "bind":
                source_path = Path(volume.source).expanduser()
                if not source_path.exists():
                    warnings.append(f"Bind mount source does not exist: {volume.source}")
    
    # Security validation
    apply_security_defaults(env)
    
    return errors, warnings
```

### Resource Preparation

```python
def prepare_resources(env: Environment) -> dict:
    """Prepare resources before container creation"""
    resources = {
        "volumes": [],
        "networks": [],
        "temp_files": []
    }
    
    docker = DockerClient()
    
    # Create named volumes
    if env.volumes:
        for volume in env.volumes:
            if volume.is_named_volume():
                try:
                    docker.create_volume(volume.name)
                    resources["volumes"].append(volume.name)
                except VolumeExistsError:
                    # Volume already exists, that's fine
                    pass
    
    # Create network if specified
    if env.network:
        try:
            docker.create_network(
                env.network.name,
                driver=env.network.driver,
                options=env.network.options
            )
            resources["networks"].append(env.network.name)
        except NetworkExistsError:
            # Network already exists
            pass
    
    # Generate SSH keys if needed
    if env.ssh or 22 in (env.ports or {}):
        private_key, public_key = generate_ssh_key_pair()
        resources["ssh_keys"] = {
            "private": private_key,
            "public": public_key
        }
    
    return resources
```

## Creation Phase

### Container Creation Flow

```python
def create_container(env: Environment, resources: dict) -> str:
    """Create Docker container with full configuration"""
    docker = DockerClient()
    
    # Generate unique container name
    container_name = generate_container_name(env.name)
    
    # Build volume configuration
    volumes = {}
    binds = []
    
    if env.volumes:
        for volume in env.volumes:
            container_path = str(volume.target)
            
            if volume.type == "bind":
                # Bind mount
                source_path = Path(volume.source).expanduser().absolute()
                bind_str = f"{source_path}:{container_path}"
                if volume.mode != "rw":
                    bind_str += f":{volume.mode}"
                binds.append(bind_str)
            else:
                # Named volume
                volumes[container_path] = {}
                bind_str = f"{volume.name}:{container_path}"
                if volume.mode != "rw":
                    bind_str += f":{volume.mode}"
                binds.append(bind_str)
    
    # Build port configuration
    exposed_ports = {}
    port_bindings = {}
    
    if env.ports:
        for container_port, host_config in env.ports.items():
            port_key = f"{container_port}/tcp"
            exposed_ports[port_key] = {}
            
            port_bindings[port_key] = [{
                "HostIp": host_config.get("HostIP", "127.0.0.1"),
                "HostPort": str(host_config.get("HostPort", container_port))
            }]
    
    # Container configuration
    config = {
        "Image": env.base_image,
        "Hostname": env.hostname or env.name,
        "User": env.user,
        "WorkingDir": env.working_dir,
        "Env": [f"{k}={v}" for k, v in (env.environment or {}).items()],
        "ExposedPorts": exposed_ports,
        "Volumes": volumes,
        "Tty": True,
        "OpenStdin": True,
        "HostConfig": {
            "Binds": binds,
            "PortBindings": port_bindings,
            "NetworkMode": env.network.name if env.network else "bridge",
            "RestartPolicy": {"Name": "no"},
            "AutoRemove": False
        }
    }
    
    # Apply command if specified
    if env.command:
        config["Cmd"] = env.command
    
    # Create container
    container_id = docker.create_container(
        name=container_name,
        config=config
    )
    
    return container_id
```

### Error Recovery

```python
def create_with_recovery(env: Environment) -> str:
    """Create container with error recovery"""
    resources = None
    container_id = None
    
    try:
        # Phase 1: Prepare resources
        resources = prepare_resources(env)
        
        # Phase 2: Create container
        container_id = create_container(env, resources)
        
        # Phase 3: Start container
        docker = DockerClient()
        docker.start_container(container_id)
        
        return container_id
        
    except Exception as e:
        # Cleanup on failure
        if container_id:
            try:
                docker.remove_container(container_id, force=True)
            except:
                pass
        
        if resources:
            cleanup_resources(resources)
        
        raise
```

## Initialization Phase

### SSH Server Setup

```python
def initialize_ssh(docker: DockerClient, container_id: str, public_key: str) -> None:
    """Initialize SSH server in container"""
    
    # Install SSH server based on distribution
    distro = detect_container_distro(docker, container_id)
    
    if distro == "debian":
        # Debian/Ubuntu
        docker.exec_run(container_id, [
            "apt-get", "update"
        ])
        docker.exec_run(container_id, [
            "apt-get", "install", "-y", "openssh-server"
        ])
    elif distro == "alpine":
        # Alpine Linux
        docker.exec_run(container_id, [
            "apk", "add", "openssh"
        ])
    elif distro == "rhel":
        # Red Hat/CentOS/Fedora
        docker.exec_run(container_id, [
            "yum", "install", "-y", "openssh-server"
        ])
    
    # Create SSH directories
    docker.exec_run(container_id, [
        "mkdir", "-p", "/var/run/sshd", "/home/dev/.ssh"
    ])
    docker.exec_run(container_id, [
        "chmod", "700", "/home/dev/.ssh"
    ])
    
    # Generate host keys
    docker.exec_run(container_id, ["ssh-keygen", "-A"])
    
    # Configure SSH daemon
    sshd_config = generate_sshd_config()
    docker.exec_run(container_id, [
        "sh", "-c", f"echo '{sshd_config}' > /etc/ssh/sshd_config"
    ])
    
    # Add authorized key
    docker.exec_run(container_id, [
        "sh", "-c", f"echo '{public_key}' > /home/dev/.ssh/authorized_keys"
    ])
    docker.exec_run(container_id, [
        "chmod", "600", "/home/dev/.ssh/authorized_keys"
    ])
    docker.exec_run(container_id, [
        "chown", "-R", "dev:dev", "/home/dev/.ssh"
    ])
    
    # Start SSH daemon
    docker.exec_run(container_id, ["/usr/sbin/sshd", "-D"], detach=True)
```

### Git Repository Setup

```python
def initialize_git_repository(docker: DockerClient, container_id: str, git_config: GitConfig) -> None:
    """Clone and configure git repository"""
    
    # Install git if needed
    output, _ = docker.exec_run(container_id, ["which", "git"])
    if not output.strip():
        install_git(docker, container_id)
    
    # Configure git
    if git_config.config:
        for key, value in git_config.config.items():
            docker.exec_run(container_id, [
                "git", "config", "--global", key, value
            ])
    
    # Clone repository
    clone_cmd = ["git", "clone"]
    
    if git_config.shallow:
        clone_cmd.extend(["--depth", "1"])
    
    if git_config.branch != "main":
        clone_cmd.extend(["--branch", git_config.branch])
    
    clone_cmd.extend([git_config.url, git_config.path])
    
    # Clone with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        output, exit_code = docker.exec_run(container_id, clone_cmd)
        
        if exit_code == 0:
            break
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
        else:
            raise GitCloneError(f"Failed to clone repository: {output}")
    
    # Set up git hooks if present
    setup_git_hooks(docker, container_id, git_config.path)
```

### Environment Initialization

```python
def initialize_environment(docker: DockerClient, container_id: str, env: Environment) -> None:
    """Complete environment initialization"""
    
    # Phase 1: System setup
    if env.ssh or 22 in (env.ports or {}):
        public_key = get_host_ssh_key()
        initialize_ssh(docker, container_id, public_key)
    
    # Phase 2: Git setup
    if env.git:
        initialize_git_repository(docker, container_id, env.git)
    
    # Phase 3: User environment setup
    setup_user_environment(docker, container_id, env)
    
    # Phase 4: Run initialization scripts
    run_init_scripts(docker, container_id, env)
    
    # Phase 5: Health check
    verify_environment_health(docker, container_id, env)
```

## Runtime Phase

### Container Monitoring

```python
class ContainerMonitor:
    """Monitor container health during runtime"""
    
    def __init__(self, container_id: str):
        self.container_id = container_id
        self.docker = DockerClient()
    
    def check_health(self) -> dict:
        """Check container health status"""
        try:
            info = self.docker.inspect_container(self.container_id)
            
            return {
                "running": info["State"]["Running"],
                "status": info["State"]["Status"],
                "exit_code": info["State"]["ExitCode"],
                "started_at": info["State"]["StartedAt"],
                "memory_usage": self._get_memory_usage(info),
                "cpu_usage": self._get_cpu_usage(info)
            }
        except ContainerNotFoundError:
            return {"running": False, "status": "removed"}
    
    def _get_memory_usage(self, info: dict) -> int:
        """Extract memory usage from container stats"""
        # Implementation depends on Docker API version
        return 0
    
    def _get_cpu_usage(self, info: dict) -> float:
        """Extract CPU usage from container stats"""
        # Implementation depends on Docker API version
        return 0.0
```

### Automatic Recovery

```python
def monitor_and_recover(container_id: str, env: Environment) -> None:
    """Monitor container and recover from failures"""
    monitor = ContainerMonitor(container_id)
    recovery_attempts = 0
    max_recoveries = 3
    
    while recovery_attempts < max_recoveries:
        health = monitor.check_health()
        
        if not health["running"]:
            if health["exit_code"] != 0:
                # Unexpected exit
                logger.warning(f"Container {container_id} exited unexpectedly")
                
                # Attempt recovery
                recovery_attempts += 1
                try:
                    recover_container(container_id, env)
                except Exception as e:
                    logger.error(f"Recovery failed: {e}")
                    if recovery_attempts >= max_recoveries:
                        raise
            else:
                # Normal exit
                break
        
        time.sleep(30)  # Check every 30 seconds

def recover_container(container_id: str, env: Environment) -> None:
    """Attempt to recover failed container"""
    docker = DockerClient()
    
    # Save current state
    state = extract_container_state(docker, container_id)
    
    # Remove failed container
    docker.remove_container(container_id, force=True)
    
    # Recreate with same configuration
    new_container_id = create_container(env, state["resources"])
    
    # Start and reinitialize
    docker.start_container(new_container_id)
    initialize_environment(docker, new_container_id, env)
    
    # Update state tracking
    update_container_mapping(container_id, new_container_id)
```

## Shutdown Phase

### Graceful Shutdown

```python
def graceful_shutdown(container_id: str, timeout: int = 30) -> None:
    """Gracefully shut down container"""
    docker = DockerClient()
    
    # Phase 1: Notify processes
    try:
        # Send SIGTERM to init process
        docker.exec_run(container_id, ["kill", "-TERM", "1"])
    except Exception:
        pass
    
    # Phase 2: Wait for graceful shutdown
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            info = docker.inspect_container(container_id)
            if not info["State"]["Running"]:
                return
        except ContainerNotFoundError:
            return
        
        time.sleep(1)
    
    # Phase 3: Force stop if needed
    docker.stop_container(container_id, timeout=10)
```

### Data Preservation

```python
def preserve_container_data(container_id: str, env: Environment) -> dict:
    """Preserve important data before shutdown"""
    docker = DockerClient()
    preserved = {
        "workspace": None,
        "config_files": [],
        "logs": None
    }
    
    # Export workspace if requested
    if should_preserve_workspace(env):
        workspace_tar = export_directory(
            docker, container_id, env.working_dir
        )
        preserved["workspace"] = workspace_tar
    
    # Save configuration files
    config_paths = [
        "/home/dev/.bashrc",
        "/home/dev/.gitconfig",
        "/home/dev/.ssh/config"
    ]
    for path in config_paths:
        try:
            content, _ = docker.exec_run(container_id, ["cat", path])
            if content:
                preserved["config_files"].append({
                    "path": path,
                    "content": content
                })
        except Exception:
            pass
    
    # Collect logs
    preserved["logs"] = docker.get_logs(container_id, tail=1000)
    
    return preserved
```

## Cleanup Phase

### Resource Cleanup

```python
def cleanup_environment(env_name: str, remove_volumes: bool = False) -> None:
    """Complete environment cleanup"""
    state_manager = StateManager()
    docker = DockerClient()
    
    # Get environment state
    env_state = state_manager.get_environment(env_name)
    if not env_state:
        raise EnvironmentNotFoundError(env_name)
    
    container_id = env_state["container_id"]
    
    # Phase 1: Stop container
    try:
        graceful_shutdown(container_id)
    except Exception as e:
        logger.warning(f"Graceful shutdown failed: {e}")
        docker.stop_container(container_id, timeout=0)
    
    # Phase 2: Remove container
    try:
        docker.remove_container(container_id)
    except ContainerNotFoundError:
        pass
    
    # Phase 3: Clean up volumes
    if remove_volumes and env_state.get("volumes"):
        for volume_name in env_state["volumes"]:
            try:
                docker.remove_volume(volume_name)
            except VolumeNotFoundError:
                pass
    
    # Phase 4: Clean up network
    if env_state.get("network"):
        try:
            # Only remove if no other containers use it
            if not is_network_in_use(env_state["network"]):
                docker.remove_network(env_state["network"])
        except NetworkNotFoundError:
            pass
    
    # Phase 5: Remove state
    state_manager.remove_environment(env_name)
    
    # Phase 6: Clean up SSH config
    remove_ssh_config(f"devenv-{env_name}")
```

### Orphan Cleanup

```python
def cleanup_orphaned_resources() -> dict:
    """Clean up orphaned Docker resources"""
    docker = DockerClient()
    cleaned = {
        "containers": 0,
        "volumes": 0,
        "networks": 0
    }
    
    # Find orphaned containers
    containers = docker.list_containers(all=True)
    for container in containers:
        if container["Names"][0].startswith("/devenv-"):
            # Check if tracked in state
            if not is_container_tracked(container["Id"]):
                docker.remove_container(container["Id"], force=True)
                cleaned["containers"] += 1
    
    # Find orphaned volumes
    volumes = docker.list_volumes()
    for volume in volumes:
        if volume["Name"].startswith("devenv-"):
            if not is_volume_tracked(volume["Name"]):
                docker.remove_volume(volume["Name"])
                cleaned["volumes"] += 1
    
    # Find orphaned networks
    networks = docker.list_networks()
    for network in networks:
        if network["Name"].startswith("devenv-"):
            if not is_network_tracked(network["Name"]):
                if not is_network_in_use(network["Name"]):
                    docker.remove_network(network["Id"])
                    cleaned["networks"] += 1
    
    return cleaned
```

## Lifecycle Hooks

### Hook System

```python
class LifecycleHooks:
    """Extensible lifecycle hook system"""
    
    def __init__(self):
        self.hooks = {
            "pre_create": [],
            "post_create": [],
            "pre_start": [],
            "post_start": [],
            "pre_stop": [],
            "post_stop": [],
            "pre_remove": [],
            "post_remove": []
        }
    
    def register_hook(self, phase: str, callback: Callable) -> None:
        """Register a lifecycle hook"""
        if phase not in self.hooks:
            raise ValueError(f"Invalid hook phase: {phase}")
        self.hooks[phase].append(callback)
    
    def run_hooks(self, phase: str, context: dict) -> None:
        """Run all hooks for a phase"""
        for hook in self.hooks[phase]:
            try:
                hook(context)
            except Exception as e:
                logger.error(f"Hook failed in {phase}: {e}")
                # Continue with other hooks
```

### Built-in Hooks

```python
def register_default_hooks(hooks: LifecycleHooks) -> None:
    """Register default lifecycle hooks"""
    
    # Logging hooks
    def log_phase(context: dict) -> None:
        phase = context["phase"]
        env_name = context["environment"].name
        logger.info(f"Lifecycle phase '{phase}' for environment '{env_name}'")
    
    for phase in hooks.hooks.keys():
        hooks.register_hook(phase, log_phase)
    
    # Security validation hook
    def validate_security(context: dict) -> None:
        env = context["environment"]
        apply_security_defaults(env)
    
    hooks.register_hook("pre_create", validate_security)
    
    # State tracking hooks
    def save_state(context: dict) -> None:
        state_manager = StateManager()
        state_manager.save_environment(
            context["environment"].name,
            context["container_state"]
        )
    
    hooks.register_hook("post_create", save_state)
    hooks.register_hook("post_remove", lambda ctx: 
        StateManager().remove_environment(ctx["environment"].name)
    )
```

## Error Handling

### Lifecycle Errors

```python
class LifecycleError(DevEnvError):
    """Base class for lifecycle errors"""
    def __init__(self, phase: str, message: str):
        self.phase = phase
        super().__init__(f"Lifecycle error in {phase}: {message}")

class CreationError(LifecycleError):
    """Container creation failed"""
    def __init__(self, message: str):
        super().__init__("creation", message)

class InitializationError(LifecycleError):
    """Container initialization failed"""
    def __init__(self, message: str):
        super().__init__("initialization", message)

class ShutdownError(LifecycleError):
    """Container shutdown failed"""
    def __init__(self, message: str):
        super().__init__("shutdown", message)
```

### Error Recovery Matrix

| Error Type | Phase | Recovery Action |
|-----------|-------|-----------------|
| Image pull failure | Creation | Retry with backoff, use local image |
| Port conflict | Creation | Suggest alternative port |
| Volume mount error | Creation | Create missing directories |
| SSH setup failure | Initialization | Retry, fall back to exec |
| Git clone failure | Initialization | Retry, provide manual instructions |
| Container crash | Runtime | Automatic restart with limits |
| Shutdown timeout | Shutdown | Force stop after grace period |
| Cleanup failure | Cleanup | Log and continue |

## Performance Considerations

### Parallel Initialization

```python
async def parallel_initialize(docker: DockerClient, container_id: str, env: Environment):
    """Initialize container components in parallel"""
    import asyncio
    
    tasks = []
    
    # SSH setup (if needed)
    if env.ssh or 22 in (env.ports or {}):
        tasks.append(async_initialize_ssh(docker, container_id))
    
    # Git clone (if configured)
    if env.git:
        tasks.append(async_clone_repository(docker, container_id, env.git))
    
    # Package installation
    if env.packages:
        tasks.append(async_install_packages(docker, container_id, env.packages))
    
    # Run all initialization tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check for failures
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            raise InitializationError(f"Task {i} failed: {result}")
```

### Caching Strategies

```python
def cache_initialization_artifacts(env: Environment) -> None:
    """Cache commonly used initialization artifacts"""
    cache_dir = Path.home() / ".dev-env" / "cache"
    
    # Cache SSH host keys
    ssh_cache = cache_dir / "ssh-keys" / env.base_image.replace(":", "_")
    ssh_cache.mkdir(parents=True, exist_ok=True)
    
    # Cache package lists
    pkg_cache = cache_dir / "package-lists" / env.base_image.replace(":", "_")
    pkg_cache.mkdir(parents=True, exist_ok=True)
    
    # Cache git repositories (bare clones)
    if env.git:
        repo_name = env.git.url.split("/")[-1].replace(".git", "")
        git_cache = cache_dir / "git" / repo_name
        if not git_cache.exists():
            subprocess.run([
                "git", "clone", "--bare", env.git.url, str(git_cache)
            ])
```

## Conclusion

The container lifecycle in dev-env is designed to be robust, recoverable, and extensible. Each phase has clear responsibilities and error handling, ensuring reliable environment management from creation to cleanup.

The lifecycle hooks provide extension points for customization without modifying core functionality, while the monitoring and recovery systems ensure environments remain available during development.

For implementation details of specific components, see:
- [Architecture Overview](overview.md)
- [Docker Client](docker-client.md)
- [State Management](state-management.md)