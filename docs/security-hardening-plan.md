# Dev-Env Security Hardening Plan (Revised)

## Overview

This plan implements essential security controls for dev-env while maintaining simplicity and developer productivity. Focus areas include container isolation, access control, and secure defaults.

## Core Security Enhancements

### 1. Container User Security

**Default Non-Root Execution**

Containers run as unprivileged user by default, preventing privilege escalation attacks.

```python
# docker.py modifications
def create_container(self, ..., user: str = None):
    if user is None:
        user = "1000:1000"  # Default non-root
    
    config["User"] = user
    config["SecurityOpt"] = ["no-new-privileges:true"]
```

**Configuration Override**

Allow explicit root access when required:

```python
# In environment configuration
environment = Environment(
    name="legacy-app",
    base_image="ubuntu:22.04",
    security=SecurityConfig(user="root")  # Explicit override
)
```

### 2. Volume Mount Protection

**Dangerous Path Prevention**

Block mounting of sensitive host directories that could compromise security.

```python
# utils.py
FORBIDDEN_MOUNT_PATHS = [
    "/",                      # Root filesystem
    "/etc",                   # System configuration
    "/var/run/docker.sock",   # Docker socket
    "/proc",                  # Process information
    "/sys",                   # Kernel interfaces
    "/dev"                    # Device files
]

def validate_volume_security(volume: VolumeMount) -> None:
    """Prevent dangerous volume mounts"""
    source_path = Path(volume.source).resolve()
    
    for forbidden in FORBIDDEN_MOUNT_PATHS:
        if str(source_path).startswith(forbidden):
            raise SecurityError(
                f"Cannot mount {forbidden}: security violation"
            )
```

### 3. Network Access Control

**Localhost-Only Port Binding**

Prevent accidental service exposure to external networks.

```python
# docker.py
def _prepare_port_bindings(self, ports: Dict[int, Any]) -> Tuple[Dict, Dict]:
    """Convert port configuration to Docker format"""
    exposed_ports = {}
    port_bindings = {}
    
    for container_port, host_config in ports.items():
        exposed_ports[f"{container_port}/tcp"] = {}
        
        if isinstance(host_config, dict):
            # Force localhost binding if not specified
            if "HostIp" not in host_config:
                host_config["HostIp"] = "127.0.0.1"
            
            # Reject all-interface binding
            if host_config["HostIp"] == "0.0.0.0":
                raise SecurityError(
                    f"Port {container_port} cannot bind to all interfaces. "
                    "Use '127.0.0.1' for localhost-only access"
                )
            
            port_bindings[f"{container_port}/tcp"] = [{
                "HostIp": host_config["HostIp"],
                "HostPort": str(host_config.get("HostPort", ""))
            }]
    
    return exposed_ports, port_bindings
```

### 4. Resource Limits

**Default Resource Constraints**

Prevent resource exhaustion and provide predictable performance.

```python
# config.py
@dataclass
class ResourceConfig:
    memory: str = "2g"        # Memory limit
    cpus: float = 2.0         # CPU limit
    pids_limit: int = 1000    # Process limit
    
    def to_docker_config(self) -> Dict[str, Any]:
        return {
            "Memory": self._parse_memory(self.memory),
            "CpuQuota": int(self.cpus * 100000),
            "PidsLimit": self.pids_limit
        }
```

### 5. Capability Management

**Minimal Capability Set**

Drop all capabilities by default, allowing explicit additions when needed.

```python
# config.py
@dataclass
class SecurityConfig:
    user: str = "1000:1000"
    drop_capabilities: List[str] = field(default_factory=lambda: ["ALL"])
    add_capabilities: List[str] = field(default_factory=list)
```

Container creation applies capability restrictions:

```python
# docker.py
if config.security.drop_capabilities:
    host_config["CapDrop"] = config.security.drop_capabilities
if config.security.add_capabilities:
    host_config["CapAdd"] = config.security.add_capabilities
```

## Security Levels

Support progressive security adoption through preset levels.

```python
# config.py
class SecurityLevel(Enum):
    RELAXED = "relaxed"    # Compatibility mode
    STANDARD = "standard"  # Recommended defaults

SECURITY_PRESETS = {
    SecurityLevel.RELAXED: SecurityConfig(
        user="root",
        drop_capabilities=[]
    ),
    SecurityLevel.STANDARD: SecurityConfig(
        user="1000:1000",
        drop_capabilities=["ALL"]
    )
}
```

Usage in environment configuration:

```python
environment = Environment(
    name="myapp",
    base_image="python:3.13",
    security_level=SecurityLevel.STANDARD  # Apply preset
)
```

## Implementation Details

### Configuration Structure

Extend Environment dataclass with security options:

```python
@dataclass
class Environment:
    # Existing fields...
    security: Optional[SecurityConfig] = None
    resources: Optional[ResourceConfig] = None
    security_level: Optional[SecurityLevel] = None
    
    def __post_init__(self):
        # Apply security preset if specified
        if self.security_level and not self.security:
            self.security = SECURITY_PRESETS[self.security_level]
        
        # Apply defaults
        if not self.security:
            self.security = SecurityConfig()
        if not self.resources:
            self.resources = ResourceConfig()
```

### SSH Security

Simplify SSH configuration to essential hardening:

```python
# utils.py
def setup_ssh_server(docker_client, container_id: str) -> None:
    """Configure SSH with basic hardening"""
    # ... installation code ...
    
    # Minimal secure configuration
    sshd_config = """
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
StrictModes yes
"""
    
    docker_client.exec_run(
        container_id, 
        ["sh", "-c", f"echo '{sshd_config}' >> /etc/ssh/sshd_config"]
    )
```

### Error Messages

Provide actionable security error messages:

```python
class SecurityError(DevEnvError):
    """Security-related errors with remediation guidance"""
    
    def __init__(self, message: str):
        remediation = "To override security restrictions, see: docs/security.md"
        super().__init__(message, remediation, exit_code=2)
```

## Migration Strategy

### Phase 1: Warnings (Week 1)
- Add security validations with warnings only
- Log insecure configurations
- Provide migration documentation

### Phase 2: Secure Defaults (Week 2)
- Enable standard security level by default
- Allow explicit overrides for compatibility
- Update example configurations

### Phase 3: Documentation (Week 3)
- Security best practices guide
- Common override scenarios
- Performance impact analysis

## Testing

### Security Test Suite

```python
# tests/test_security.py
def test_non_root_default():
    """Verify containers use non-root user by default"""
    env = Environment(name="test", base_image="alpine")
    assert env.security.user == "1000:1000"

def test_forbidden_mount_rejection():
    """Ensure dangerous mounts are blocked"""
    with pytest.raises(SecurityError):
        validate_volume_security(
            VolumeMount(source="/etc", target="/host-etc")
        )

def test_localhost_port_binding():
    """Verify ports bind to localhost only"""
    ports = prepare_port_bindings({80: {"HostPort": 8080}})
    assert ports[1]["80/tcp"][0]["HostIp"] == "127.0.0.1"

def test_capability_dropping():
    """Ensure ALL capabilities dropped by default"""
    env = Environment(name="test", base_image="alpine")
    assert "ALL" in env.security.drop_capabilities
```

## Documentation

### Security Configuration Guide

Document common security scenarios:

1. **Running as root** (when required):
   ```python
   security=SecurityConfig(user="root")
   ```

2. **Adding specific capabilities**:
   ```python
   security=SecurityConfig(
       add_capabilities=["NET_ADMIN", "SYS_TIME"]
   )
   ```

3. **Increasing resource limits**:
   ```python
   resources=ResourceConfig(memory="8g", cpus=4.0)
   ```

4. **Exposing to network** (with caution):
   ```python
   ports={80: {"HostIp": "0.0.0.0", "HostPort": 8080}}
   ```

### Security Considerations

Document security tradeoffs:

- Non-root execution may break some tools
- Capability restrictions affect system utilities
- Resource limits prevent runaway processes
- Localhost binding blocks remote access

## Summary

This revised plan delivers essential security improvements without compromising dev-env's core values:

- **Pragmatic**: Focuses on high-impact, low-complexity features
- **Compatible**: Provides escape hatches for legacy requirements  
- **Simple**: Maintains zero-dependency architecture
- **Transparent**: Clear error messages and documentation

Total implementation effort: ~1 week for core features, 1 week for testing and documentation.