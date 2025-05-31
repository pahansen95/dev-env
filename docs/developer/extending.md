# Extension Patterns

This guide demonstrates how to extend dev-env for custom use cases, including custom base images, configuration templates, and integration patterns.

## Custom Base Images

### Creating Custom Development Images

#### Basic Python Development Image

```dockerfile
# images/python-dev.dockerfile
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ssh \
    curl \
    vim \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create development user
RUN useradd -m -s /bin/bash dev && \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Install common Python tools
RUN pip install --no-cache-dir \
    black \
    flake8 \
    mypy \
    pytest \
    pytest-cov \
    ipython

# Setup SSH
RUN mkdir -p /home/dev/.ssh && \
    chown -R dev:dev /home/dev/.ssh && \
    chmod 700 /home/dev/.ssh

USER dev
WORKDIR /workspace

# Setup shell
RUN echo 'alias ll="ls -la"' >> /home/dev/.bashrc && \
    echo 'alias la="ls -A"' >> /home/dev/.bashrc && \
    echo 'export PS1="\u@\h:\w$ "' >> /home/dev/.bashrc
```

Build and use:
```bash
# Build image
docker build -f images/python-dev.dockerfile -t myorg/python-dev:latest .

# Use in configuration
environment = Environment(
    name="myproject",
    base_image="myorg/python-dev:latest"
)
```

#### Node.js Development Image

```dockerfile
# images/node-dev.dockerfile
FROM node:20-slim

# Install system tools
RUN apt-get update && apt-get install -y \
    git \
    ssh \
    curl \
    vim \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install global Node.js tools
RUN npm install -g \
    nodemon \
    eslint \
    prettier \
    @typescript-eslint/parser \
    typescript

# Create development user
RUN useradd -m -s /bin/bash dev && \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Setup directories
RUN mkdir -p /home/dev/.ssh /app && \
    chown -R dev:dev /home/dev /app

USER dev
WORKDIR /app
```

#### Multi-Language Development Image

```dockerfile
# images/polyglot-dev.dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ssh \
    vim \
    build-essential \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install Python
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.13 python3.13-pip

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install Go
RUN curl -fsSL https://golang.org/dl/go1.21.0.linux-amd64.tar.gz | \
    tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:${PATH}"

# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Create development user
RUN useradd -m -s /bin/bash dev && \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER dev
WORKDIR /workspace
```

### Language-Specific Extensions

#### Rust Development

```python
# templates/rust.py
from dev_env.config import Environment, GitConfig, VolumeMount

def create_rust_env(name: str, repo_url: str) -> Environment:
    return Environment(
        name=name,
        base_image="rust:1.75",
        git=GitConfig(url=repo_url),
        volumes=[
            VolumeMount(source=".", target="/workspace"),
            VolumeMount(
                source=f"{name}-cargo-cache",
                target="/usr/local/cargo/registry",
                type="named"
            ),
            VolumeMount(
                source=f"{name}-target-cache",
                target="/workspace/target",
                type="named"
            )
        ],
        environment={
            "RUST_BACKTRACE": "1"
        },
        command=["bash"]
    )
```

#### Go Development

```python
# templates/golang.py
from dev_env.config import Environment, GitConfig, VolumeMount

def create_go_env(name: str, repo_url: str, go_version: str = "1.21") -> Environment:
    return Environment(
        name=name,
        base_image=f"golang:{go_version}",
        git=GitConfig(url=repo_url),
        volumes=[
            VolumeMount(source=".", target="/workspace"),
            VolumeMount(
                source=f"{name}-go-cache",
                target="/go/pkg/mod",
                type="named"
            )
        ],
        environment={
            "GO111MODULE": "on",
            "GOPROXY": "https://proxy.golang.org"
        },
        working_dir="/workspace"
    )
```

## Configuration Templates

### Template Library

Create a reusable template library:

```python
# templates/__init__.py
from .python import create_python_env
from .node import create_node_env
from .database import create_postgres_env, create_redis_env
from .web import create_web_stack

__all__ = [
    'create_python_env',
    'create_node_env', 
    'create_postgres_env',
    'create_redis_env',
    'create_web_stack'
]
```

```python
# templates/python.py
from dev_env.config import Environment, GitConfig, VolumeMount
from typing import Optional, Dict, List

def create_python_env(
    name: str,
    repo_url: str,
    python_version: str = "3.13",
    port: int = 8000,
    environment_vars: Optional[Dict[str, str]] = None,
    extra_volumes: Optional[List[VolumeMount]] = None
) -> Environment:
    """Create standardized Python development environment"""
    
    volumes = [
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source=f"{name}-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ]
    
    if extra_volumes:
        volumes.extend(extra_volumes)
    
    env_vars = {
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1"
    }
    if environment_vars:
        env_vars.update(environment_vars)
    
    return Environment(
        name=name,
        base_image=f"python:{python_version}",
        git=GitConfig(url=repo_url),
        ports={
            22: {"HostPort": 2222},
            port: {"HostPort": port}
        },
        volumes=volumes,
        environment=env_vars,
        working_dir="/app"
    )

def create_django_env(name: str, repo_url: str, **kwargs) -> Environment:
    """Django-specific Python environment"""
    django_vars = {
        "DJANGO_SETTINGS_MODULE": f"{name}.settings.development",
        "DJANGO_DEBUG": "True"
    }
    
    existing_vars = kwargs.get('environment_vars', {})
    kwargs['environment_vars'] = {**django_vars, **existing_vars}
    
    return create_python_env(name, repo_url, **kwargs)

def create_fastapi_env(name: str, repo_url: str, **kwargs) -> Environment:
    """FastAPI-specific Python environment"""
    fastapi_vars = {
        "ENVIRONMENT": "development",
        "RELOAD": "true"
    }
    
    existing_vars = kwargs.get('environment_vars', {})
    kwargs['environment_vars'] = {**fastapi_vars, **existing_vars}
    
    env = create_python_env(name, repo_url, **kwargs)
    env.command = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]
    
    return env
```

```python
# templates/database.py
from dev_env.config import Environment, VolumeMount, NetworkConfig
from typing import Optional

def create_postgres_env(
    name: str,
    db_name: str = "devdb",
    user: str = "devuser",
    password: str = "devpass",
    network: Optional[NetworkConfig] = None
) -> Environment:
    """Create PostgreSQL database environment"""
    return Environment(
        name=f"{name}-postgres",
        base_image="postgres:16-alpine",
        network=network,
        ports={
            5432: {"HostPort": 5432}
        },
        volumes=[
            VolumeMount(
                source=f"{name}-postgres-data",
                target="/var/lib/postgresql/data",
                type="named"
            )
        ],
        environment={
            "POSTGRES_DB": db_name,
            "POSTGRES_USER": user,
            "POSTGRES_PASSWORD": password
        }
    )

def create_redis_env(
    name: str,
    network: Optional[NetworkConfig] = None
) -> Environment:
    """Create Redis cache environment"""
    return Environment(
        name=f"{name}-redis",
        base_image="redis:7-alpine",
        network=network,
        ports={
            6379: {"HostPort": 6379}
        },
        volumes=[
            VolumeMount(
                source=f"{name}-redis-data",
                target="/data",
                type="named"
            )
        ],
        command=["redis-server", "--appendonly", "yes"]
    )
```

### Dynamic Configuration Generation

```python
# templates/generator.py
from dev_env.config import Environment, NetworkConfig
from .python import create_python_env, create_django_env
from .database import create_postgres_env, create_redis_env
from typing import Dict, Any, List

class StackGenerator:
    """Generate complete application stacks"""
    
    def __init__(self, project_name: str):
        self.project_name = project_name
        self.network = NetworkConfig(name=f"{project_name}-network")
    
    def django_stack(
        self,
        repo_url: str,
        with_redis: bool = True,
        with_postgres: bool = True
    ) -> Dict[str, Environment]:
        """Generate complete Django stack"""
        
        environments = {}
        
        # Database
        if with_postgres:
            environments['db'] = create_postgres_env(
                self.project_name,
                network=self.network
            )
        
        # Cache
        if with_redis:
            environments['cache'] = create_redis_env(
                self.project_name,
                network=self.network
            )
        
        # Web application
        db_url = f"postgresql://devuser:devpass@{self.project_name}-postgres:5432/devdb" if with_postgres else "sqlite:///db.sqlite3"
        redis_url = f"redis://{self.project_name}-redis:6379/0" if with_redis else None
        
        env_vars = {"DATABASE_URL": db_url}
        if redis_url:
            env_vars["REDIS_URL"] = redis_url
        
        environments['web'] = create_django_env(
            self.project_name,
            repo_url,
            environment_vars=env_vars
        )
        environments['web'].network = self.network
        
        return environments
    
    def microservice_stack(
        self,
        services: List[Dict[str, Any]]
    ) -> Dict[str, Environment]:
        """Generate microservice stack"""
        
        environments = {}
        
        # Shared infrastructure
        environments['db'] = create_postgres_env(
            self.project_name,
            network=self.network
        )
        environments['cache'] = create_redis_env(
            self.project_name,
            network=self.network
        )
        
        # Services
        for i, service in enumerate(services):
            service_name = service['name']
            port_offset = i * 10
            
            env = create_python_env(
                f"{self.project_name}-{service_name}",
                service['repo_url'],
                port=8000 + port_offset,
                environment_vars={
                    "SERVICE_NAME": service_name,
                    "DATABASE_URL": f"postgresql://devuser:devpass@{self.project_name}-postgres:5432/devdb",
                    "REDIS_URL": f"redis://{self.project_name}-redis:6379/{i}"
                }
            )
            env.network = self.network
            environments[service_name] = env
        
        return environments

# Usage
generator = StackGenerator("myapp")

# Generate Django stack
django_envs = generator.django_stack(
    "git@github.com:org/myapp.git",
    with_redis=True,
    with_postgres=True
)

# Generate microservice stack
microservice_envs = generator.microservice_stack([
    {"name": "auth", "repo_url": "git@github.com:org/auth-service.git"},
    {"name": "api", "repo_url": "git@github.com:org/api-service.git"},
    {"name": "worker", "repo_url": "git@github.com:org/worker-service.git"}
])
```

## Hook Mechanisms

### Pre/Post Environment Hooks

```python
# hooks/lifecycle.py
import subprocess
import logging
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class EnvironmentHooks:
    """Hook system for environment lifecycle events"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.hooks_dir = project_dir / "hooks"
    
    def run_hook(self, hook_name: str, env_name: str) -> bool:
        """Run a specific hook script"""
        hook_script = self.hooks_dir / f"{hook_name}.sh"
        
        if not hook_script.exists():
            logger.debug(f"Hook {hook_name} not found, skipping")
            return True
        
        try:
            result = subprocess.run(
                [str(hook_script), env_name],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Hook {hook_name} completed successfully")
                return True
            else:
                logger.error(f"Hook {hook_name} failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Hook {hook_name} timed out")
            return False
        except Exception as e:
            logger.error(f"Error running hook {hook_name}: {e}")
            return False
    
    def pre_create(self, env_name: str) -> bool:
        """Run before environment creation"""
        return self.run_hook("pre-create", env_name)
    
    def post_create(self, env_name: str) -> bool:
        """Run after environment creation"""
        return self.run_hook("post-create", env_name)
    
    def pre_destroy(self, env_name: str) -> bool:
        """Run before environment destruction"""
        return self.run_hook("pre-destroy", env_name)
    
    def post_destroy(self, env_name: str) -> bool:
        """Run after environment destruction"""
        return self.run_hook("post-destroy", env_name)

# Extended environment with hooks
class HookedEnvironment(Environment):
    """Environment that supports lifecycle hooks"""
    
    def __init__(self, *args, hooks_enabled: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.hooks_enabled = hooks_enabled
        self._hooks = EnvironmentHooks(Path.cwd()) if hooks_enabled else None
    
    def create(self):
        """Create environment with hooks"""
        if self._hooks:
            if not self._hooks.pre_create(self.name):
                raise RuntimeError("Pre-create hook failed")
        
        # Standard creation logic here
        super().create()
        
        if self._hooks:
            if not self._hooks.post_create(self.name):
                logger.warning("Post-create hook failed")
    
    def destroy(self):
        """Destroy environment with hooks"""
        if self._hooks:
            if not self._hooks.pre_destroy(self.name):
                logger.warning("Pre-destroy hook failed")
        
        # Standard destruction logic here
        super().destroy()
        
        if self._hooks:
            if not self._hooks.post_destroy(self.name):
                logger.warning("Post-destroy hook failed")
```

### Example Hook Scripts

```bash
#!/bin/bash
# hooks/pre-create.sh
set -e

ENV_NAME=$1
echo "Preparing environment: $ENV_NAME"

# Create necessary directories
mkdir -p ./logs
mkdir -p ./data
mkdir -p ./backups

# Download dependencies
echo "Downloading dependencies..."
curl -fsSL https://example.com/setup.sh | bash

echo "Pre-create hook completed for $ENV_NAME"
```

```bash
#!/bin/bash
# hooks/post-create.sh
set -e

ENV_NAME=$1
echo "Configuring environment: $ENV_NAME"

# Wait for environment to be ready
echo "Waiting for environment to be ready..."
for i in {1..30}; do
    if dev-env exec $ENV_NAME echo "ready" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

# Install dependencies
echo "Installing dependencies..."
dev-env exec $ENV_NAME pip install -r requirements.txt

# Run initial setup
echo "Running initial setup..."
dev-env exec $ENV_NAME python manage.py migrate

echo "Post-create hook completed for $ENV_NAME"
```

## Network Architecture Extensions

### Custom Network Drivers

```python
# network/custom.py
from dev_env.config import NetworkConfig, Environment
from typing import List, Dict, Any

class OverlayNetworkConfig(NetworkConfig):
    """Custom overlay network for multi-host setups"""
    
    def __init__(
        self,
        name: str,
        subnet: str = "10.0.0.0/24",
        attachable: bool = True,
        encrypted: bool = False
    ):
        super().__init__(name=name, driver="overlay")
        self.subnet = subnet
        self.attachable = attachable
        self.encrypted = encrypted
    
    def to_docker_config(self) -> Dict[str, Any]:
        """Convert to Docker network creation config"""
        config = {
            "Name": self.name,
            "Driver": self.driver,
            "IPAM": {
                "Config": [{"Subnet": self.subnet}]
            },
            "Attachable": self.attachable
        }
        
        if self.encrypted:
            config["Options"] = {"encrypted": "true"}
        
        return config

class ServiceMeshNetwork:
    """Service mesh networking for microservices"""
    
    def __init__(self, mesh_name: str):
        self.mesh_name = mesh_name
        self.frontend_network = NetworkConfig(f"{mesh_name}-frontend")
        self.backend_network = NetworkConfig(f"{mesh_name}-backend")
    
    def create_frontend_service(self, name: str, **kwargs) -> Environment:
        """Create frontend service connected to frontend network"""
        env = Environment(name=name, network=self.frontend_network, **kwargs)
        return env
    
    def create_backend_service(self, name: str, **kwargs) -> Environment:
        """Create backend service connected to backend network"""
        env = Environment(name=name, network=self.backend_network, **kwargs)
        return env
    
    def create_gateway_service(self, name: str, **kwargs) -> Environment:
        """Create gateway service connected to both networks"""
        # Note: This would require custom Docker client implementation
        # to attach container to multiple networks
        env = Environment(name=name, network=self.frontend_network, **kwargs)
        # Additional logic to attach to backend network
        return env
```

### Load Balancer Integration

```python
# network/loadbalancer.py
from dev_env.config import Environment, NetworkConfig
from typing import List, Dict

class LoadBalancerConfig:
    """Configuration for load balancer"""
    
    def __init__(
        self,
        name: str,
        backend_services: List[str],
        algorithm: str = "round_robin",
        health_check_path: str = "/health"
    ):
        self.name = name
        self.backend_services = backend_services
        self.algorithm = algorithm
        self.health_check_path = health_check_path
    
    def generate_haproxy_config(self) -> str:
        """Generate HAProxy configuration"""
        config = f"""
global
    daemon

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms

frontend web_frontend
    bind *:80
    default_backend web_servers

backend web_servers
    balance {self.algorithm}
    option httpchk GET {self.health_check_path}
"""
        
        for i, service in enumerate(self.backend_services):
            config += f"    server web{i+1} {service}:8000 check\n"
        
        return config

def create_load_balanced_stack(
    project_name: str,
    service_count: int = 3,
    repo_url: str = ""
) -> Dict[str, Environment]:
    """Create load-balanced application stack"""
    
    network = NetworkConfig(f"{project_name}-lb-network")
    environments = {}
    service_names = []
    
    # Create backend services
    for i in range(service_count):
        service_name = f"{project_name}-web-{i+1}"
        service_names.append(service_name)
        
        environments[f"web-{i+1}"] = Environment(
            name=service_name,
            base_image="python:3.13",
            network=network,
            git=GitConfig(url=repo_url),
            environment={
                "INSTANCE_ID": str(i+1),
                "PORT": "8000"
            }
        )
    
    # Create load balancer
    lb_config = LoadBalancerConfig(
        f"{project_name}-lb",
        service_names
    )
    
    environments['loadbalancer'] = Environment(
        name=f"{project_name}-lb",
        base_image="haproxy:2.8",
        network=network,
        ports={
            80: {"HostPort": 8080},
            8404: {"HostPort": 8404}  # HAProxy stats
        },
        volumes=[
            VolumeMount(
                source=lb_config.generate_haproxy_config(),
                target="/usr/local/etc/haproxy/haproxy.cfg",
                type="bind"
            )
        ]
    )
    
    return environments
```

## Volume Strategies

### Custom Volume Drivers

```python
# storage/drivers.py
from dev_env.config import VolumeMount
from typing import Dict, Any, Optional

class NFSVolumeMount(VolumeMount):
    """NFS volume mount for shared storage"""
    
    def __init__(
        self,
        nfs_server: str,
        nfs_path: str,
        target: str,
        mode: str = "rw",
        mount_options: Optional[str] = None
    ):
        # Use a custom source format
        source = f"nfs://{nfs_server}{nfs_path}"
        super().__init__(source=source, target=target, mode=mode, type="nfs")
        self.nfs_server = nfs_server
        self.nfs_path = nfs_path
        self.mount_options = mount_options or "rsize=8192,wsize=8192,timeo=14"
    
    def to_docker_mount(self) -> Dict[str, Any]:
        """Convert to Docker mount specification"""
        return {
            "Type": "volume",
            "Source": f"nfs-{self.nfs_server.replace('.', '-')}-{self.nfs_path.replace('/', '-')}",
            "Target": self.target,
            "VolumeOptions": {
                "DriverConfig": {
                    "Name": "local",
                    "Options": {
                        "type": "nfs",
                        "o": f"addr={self.nfs_server},{self.mount_options}",
                        "device": f":{self.nfs_path}"
                    }
                }
            }
        }

class S3VolumeMount(VolumeMount):
    """S3-backed volume using s3fs"""
    
    def __init__(
        self,
        bucket: str,
        target: str,
        aws_access_key: str,
        aws_secret_key: str,
        region: str = "us-east-1"
    ):
        source = f"s3://{bucket}"
        super().__init__(source=source, target=target, type="s3")
        self.bucket = bucket
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region = region
```

### Backup and Restore Strategies

```python
# storage/backup.py
import subprocess
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

class VolumeBackupManager:
    """Manage volume backups and restores"""
    
    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def backup_volume(self, volume_name: str, environment_name: str) -> Path:
        """Create backup of named volume"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{environment_name}_{volume_name}_{timestamp}.tar.gz"
        
        # Create temporary container to access volume
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{volume_name}:/volume",
            "-v", f"{self.backup_dir}:/backup",
            "alpine:latest",
            "tar", "-czf", f"/backup/{backup_file.name}", "-C", "/volume", "."
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Backup failed: {result.stderr}")
        
        return backup_file
    
    def restore_volume(self, backup_file: Path, volume_name: str) -> bool:
        """Restore volume from backup"""
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        # Create volume if it doesn't exist
        subprocess.run(["docker", "volume", "create", volume_name], 
                      capture_output=True)
        
        # Restore from backup
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{volume_name}:/volume",
            "-v", f"{backup_file.parent}:/backup",
            "alpine:latest",
            "tar", "-xzf", f"/backup/{backup_file.name}", "-C", "/volume"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    
    def list_backups(self, environment_name: str = None) -> List[Dict]:
        """List available backups"""
        pattern = f"{environment_name}_*" if environment_name else "*"
        backups = []
        
        for backup_file in self.backup_dir.glob(f"{pattern}.tar.gz"):
            parts = backup_file.stem.split("_")
            if len(parts) >= 3:
                backups.append({
                    "file": backup_file,
                    "environment": parts[0],
                    "volume": parts[1],
                    "timestamp": "_".join(parts[2:]),
                    "size": backup_file.stat().st_size
                })
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)

# Usage
backup_manager = VolumeBackupManager(Path("./backups"))

# Backup volumes before environment changes
backup_manager.backup_volume("myapp-data", "myapp")

# List available backups
backups = backup_manager.list_backups("myapp")
print(f"Found {len(backups)} backups")

# Restore from backup
if backups:
    latest_backup = backups[0]
    backup_manager.restore_volume(latest_backup["file"], "myapp-data-restored")
```

This extension guide provides comprehensive patterns for customizing and extending dev-env for various use cases. For API details, see the [API Reference](api-reference.md).