# Security Model

This document details dev-env's security implementation, threat model, and security controls for compliance and auditing purposes.

## Security Philosophy

Dev-env implements a **defense-in-depth** security model with the following principles:

1. **Secure by Default**: Environments start with restrictive security settings
2. **Principle of Least Privilege**: Containers run with minimal required permissions
3. **Isolation First**: Strong container and network isolation
4. **Explicit Configuration**: Security settings must be explicitly configured
5. **Auditability**: All security-relevant actions are logged and traceable

## Threat Model

### Assets Protected

- **Host System**: Prevention of container escape and privilege escalation
- **Host Data**: Protection of sensitive files and directories
- **Network**: Isolation of container networks from host and external networks
- **Credentials**: SSH keys, API tokens, and other authentication materials
- **Source Code**: Prevention of unauthorized access to repositories

### Threat Actors

1. **Malicious Code**: Untrusted code running inside containers
2. **Network Attackers**: External actors attempting network access
3. **Insider Threats**: Compromised development environments
4. **Supply Chain**: Malicious base images or dependencies

### Attack Vectors

- Container escape vulnerabilities
- Privilege escalation through misconfiguration
- Network-based attacks on exposed services
- Volume mount abuse for host file access
- SSH key compromise
- Image-based supply chain attacks

## Security Controls

### Container Isolation

#### Non-Root User Execution

All containers run as non-root users by default:

```python
# Default security configuration
environment = Environment(
    name="secure-app",
    base_image="python:3.13",
    user="1000:1000"  # Non-root user (dev:dev)
)
```

**Implementation:**
- User ID 1000 with group ID 1000 (standard non-root)
- Sudo access provided only when explicitly configured
- Home directory `/home/dev` with proper ownership

#### Security Levels

Dev-env provides predefined security levels:

```python
from dev_env.config import Environment, SecurityLevel

# Relaxed security (development only)
relaxed_env = Environment(
    name="dev-app",
    base_image="ubuntu:22.04",
    security_level=SecurityLevel.RELAXED,
    user="root"  # Override default for debugging
)

# Standard security (recommended)
standard_env = Environment(
    name="prod-app", 
    base_image="ubuntu:22.04",
    security_level=SecurityLevel.STANDARD,
    # user="1000:1000" automatically applied
)

# Strict security (production)
strict_env = Environment(
    name="secure-app",
    base_image="ubuntu:22.04",
    security_level=SecurityLevel.STRICT,
    cap_drop=["ALL"],
    cap_add=["NET_BIND_SERVICE"],
    read_only=True
)
```

#### Capability Management

Linux capabilities are restricted by default:

```python
environment = Environment(
    name="restricted-app",
    base_image="python:3.13",
    cap_drop=["ALL"],  # Drop all capabilities
    cap_add=[
        "NET_BIND_SERVICE",  # Bind to privileged ports
        "SYS_PTRACE"         # Debugging tools only
    ],
    security_opt=[
        "no-new-privileges:true",  # Prevent privilege escalation
        "seccomp=unconfined"       # Custom seccomp profile
    ]
)
```

**Default Dropped Capabilities:**
- `SYS_ADMIN` - System administration
- `SYS_PTRACE` - Process tracing (except when explicitly added)
- `NET_ADMIN` - Network administration
- `SYS_MODULE` - Kernel module loading
- `SYS_RAWIO` - Raw I/O access

### Network Security

#### Port Binding Restrictions

Ports are bound to localhost only by default:

```python
# Secure: localhost only
environment = Environment(
    name="web-app",
    base_image="nginx:alpine", 
    ports={
        80: {"HostPort": 8080, "HostIP": "127.0.0.1"}  # Explicit localhost
    }
)

# WARNING: Insecure - all interfaces
environment = Environment(
    name="public-app",
    base_image="nginx:alpine",
    ports={
        80: {"HostPort": 8080, "HostIP": "0.0.0.0"}  # Security violation
    }
)
```

**Validation Rules:**
- All port bindings default to `127.0.0.1`
- Binding to `0.0.0.0` requires explicit security override
- Privileged ports (< 1024) require special capabilities

#### Network Isolation

Containers use isolated Docker networks:

```python
from dev_env.config import NetworkConfig

# Isolated application network
app_network = NetworkConfig(
    name="secure-network",
    driver="bridge",
    internal=True,  # No external internet access
    ipv6=False      # Disable IPv6 for simplicity
)

environment = Environment(
    name="isolated-app",
    base_image="python:3.13",
    network=app_network
)
```

### SSH Security

#### Key-Based Authentication Only

SSH access uses public key authentication exclusively:

```python
from dev_env.config import SSHConfig

environment = Environment(
    name="ssh-app",
    base_image="ubuntu:22.04",
    ssh=SSHConfig(
        enabled=True,
        port=2222,
        password_auth=False,  # Disabled by default
        authorized_keys=[
            "ssh-rsa AAAAB3NzaC1yc2E... user@host",
            "ssh-ed25519 AAAAC3NzaC1lZDI... admin@host"
        ]
    )
)
```

**SSH Security Features:**
- Password authentication disabled
- Root login disabled
- SSH keys automatically injected from host
- Host key verification enabled
- Connection timeout enforced

#### SSH Server Configuration

Automatically generated `/etc/ssh/sshd_config`:

```
Port 22
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile /home/dev/.ssh/authorized_keys
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding yes
PrintMotd no
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
```

### Volume Mount Security

#### Forbidden Mount Paths

Critical system directories are protected:

```python
# Forbidden mount sources (will be rejected)
FORBIDDEN_MOUNTS = [
    "/",
    "/etc",
    "/usr", 
    "/bin",
    "/sbin",
    "/boot",
    "/sys",
    "/proc",
    "/dev",
    "/var/run/docker.sock"  # Docker socket
]
```

**Security Validation:**
```python
# This will be rejected
environment = Environment(
    name="unsafe-app",
    base_image="alpine:latest",
    volumes=[
        VolumeMount(
            source="/etc",  # SECURITY VIOLATION
            target="/host-etc"
        )
    ]
)
```

#### Safe Volume Patterns

```python
# Safe: Project directory only
environment = Environment(
    name="safe-app",
    base_image="python:3.13",
    volumes=[
        # Current project directory
        VolumeMount(source=".", target="/app"),
        
        # Named volume for data
        VolumeMount(
            source="app-data",
            target="/app/data", 
            type="named"
        ),
        
        # Read-only configuration
        VolumeMount(
            source="./config",
            target="/app/config",
            mode="ro"
        ),
        
        # User's SSH keys (read-only)
        VolumeMount(
            source="~/.ssh",
            target="/home/dev/.ssh",
            mode="ro"
        )
    ]
)
```

### Credential Management

#### SSH Agent Forwarding

SSH agent forwarding allows secure key usage without copying:

```bash
# SSH with agent forwarding (enabled by default)
dev-env ssh myproject

# Inside container, git operations use forwarded keys
git clone git@github.com:private/repo.git
```

**Implementation:**
- SSH agent socket forwarded into container
- No private keys stored in container filesystem
- Agent forwarding can be disabled if needed

#### Secret Injection

Secrets are injected at runtime, never in images:

```python
# Secure secret injection
environment = Environment(
    name="api-service",
    base_image="python:3.13",
    volumes=[
        # Inject secrets from secure storage
        VolumeMount(
            source="/secure/vault/api-keys",
            target="/app/secrets",
            mode="ro"
        )
    ],
    environment={
        # Reference secrets by path, not value
        "API_KEY_FILE": "/app/secrets/api.key",
        "DB_PASSWORD_FILE": "/app/secrets/db.password"
    }
)
```

#### Environment Variable Security

```python
# Secure environment variable patterns
environment = Environment(
    name="secure-service",
    base_image="python:3.13",
    environment={
        # Safe: Non-sensitive configuration
        "DEBUG": "false",
        "LOG_LEVEL": "info",
        
        # Safe: Reference to secret files
        "DATABASE_PASSWORD_FILE": "/secrets/db.password",
        
        # AVOID: Secrets in environment variables
        # "API_KEY": "secret-value-here",  # DON'T DO THIS
    }
)
```

## Security Monitoring

### Audit Logging

All security-relevant events are logged:

```python
import logging

# Security event logging
security_logger = logging.getLogger('dev-env.security')

def log_security_event(event_type: str, details: dict):
    """Log security events for audit"""
    security_logger.warning(f"SECURITY: {event_type}", extra={
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'details': details
    })

# Example logged events
log_security_event('MOUNT_VIOLATION', {
    'source': '/etc',
    'environment': 'myapp',
    'blocked': True
})

log_security_event('ROOT_USER_REQUESTED', {
    'environment': 'debug-app',
    'user': 'developer',
    'approved': False
})
```

### Security Metrics

Track security-relevant metrics:

```python
from prometheus_client import Counter, Gauge

# Security metrics
security_violations = Counter('dev_env_security_violations_total', 
                            'Security violations blocked', 
                            ['violation_type'])

root_containers = Gauge('dev_env_root_containers_total',
                       'Containers running as root')

exposed_ports = Gauge('dev_env_exposed_ports_total', 
                     'Ports exposed to all interfaces')

# Track violations
security_violations.labels('forbidden_mount').inc()
security_violations.labels('all_interface_binding').inc()
```

## Compliance Considerations

### Common Compliance Frameworks

#### SOC 2 Type II

Dev-env supports SOC 2 compliance through:

- **Security**: Container isolation, capability restrictions, network segmentation
- **Availability**: Resource limits, health checks, automatic recovery
- **Confidentiality**: Encrypted communications, access controls, audit logging
- **Processing Integrity**: Input validation, configuration verification, rollback capabilities
- **Privacy**: Data isolation, secure deletion, access logging

#### GDPR

Data protection features:

- **Data Minimization**: Only necessary data is exposed to containers
- **Right to Erasure**: Complete environment and volume deletion
- **Data Portability**: Export environment configurations and data
- **Privacy by Design**: Secure defaults, explicit consent for data sharing

#### ISO 27001

Information security controls:

- **Access Control**: Role-based environment access, SSH key management
- **Network Security**: Isolated networks, port restrictions, traffic monitoring
- **Incident Management**: Security event logging, automated responses
- **Risk Management**: Security level enforcement, vulnerability scanning

### Audit Requirements

#### Configuration Auditing

```python
# Track all configuration changes
def audit_config_change(old_config: dict, new_config: dict, user: str):
    """Audit configuration changes"""
    changes = {}
    
    # Track security-relevant changes
    security_fields = ['user', 'ports', 'volumes', 'cap_add', 'cap_drop']
    
    for field in security_fields:
        if old_config.get(field) != new_config.get(field):
            changes[field] = {
                'old': old_config.get(field),
                'new': new_config.get(field)
            }
    
    if changes:
        audit_logger.info("Configuration change", extra={
            'user': user,
            'changes': changes,
            'timestamp': datetime.utcnow().isoformat()
        })
```

#### Access Logging

```python
# Log all environment access
def log_environment_access(env_name: str, user: str, action: str):
    """Log environment access for audit trail"""
    access_logger.info(f"Environment access: {action}", extra={
        'environment': env_name,
        'user': user,
        'action': action,
        'timestamp': datetime.utcnow().isoformat(),
        'source_ip': get_client_ip()
    })

# Usage
log_environment_access('production-api', 'admin', 'ssh_connect')
log_environment_access('development', 'developer', 'container_create')
```

## Security Best Practices

### Development Environments

1. **Use Non-Root Users**: Always run as unprivileged users
2. **Limit Network Exposure**: Bind ports to localhost only
3. **Minimize Volume Mounts**: Only mount necessary directories
4. **Regular Updates**: Keep base images updated
5. **Scan Images**: Use vulnerability scanners on custom images

### Production Environments

1. **Strict Security Level**: Use `SecurityLevel.STRICT`
2. **Read-Only Filesystems**: Set `read_only=True` where possible
3. **Capability Restrictions**: Drop all capabilities, add only necessary ones
4. **Network Isolation**: Use internal networks without internet access
5. **Audit Everything**: Enable comprehensive logging

### Secret Management

1. **Never Embed Secrets**: Don't put secrets in configurations or images
2. **Use Secret Files**: Mount secrets as read-only files
3. **Rotate Regularly**: Implement secret rotation procedures
4. **Audit Access**: Log all secret access and usage

## Security Incident Response

### Detection

```python
# Security monitoring
def detect_security_anomalies():
    """Detect potential security issues"""
    
    # Check for root containers
    root_containers = get_containers_by_user('root')
    if root_containers:
        alert_security_team('Root containers detected', root_containers)
    
    # Check for exposed ports
    exposed_ports = get_ports_bound_to_all_interfaces()
    if exposed_ports:
        alert_security_team('Ports exposed to all interfaces', exposed_ports)
    
    # Check for suspicious volume mounts
    suspicious_mounts = get_mounts_to_system_directories()
    if suspicious_mounts:
        alert_security_team('Suspicious volume mounts', suspicious_mounts)
```

### Response Procedures

1. **Immediate Containment**: Stop affected environments
2. **Investigation**: Analyze logs and configurations
3. **Remediation**: Apply security patches or configuration fixes
4. **Recovery**: Restart environments with secure configurations
5. **Post-Incident**: Update security controls and documentation

### Emergency Shutdown

```bash
#!/bin/bash
# emergency-shutdown.sh
# Emergency security shutdown procedure

echo "EMERGENCY: Shutting down all dev-env containers"

# Stop all dev-env containers
dev-env list | grep -v "NAME" | awk '{print $1}' | while read env_name; do
    echo "Stopping environment: $env_name"
    dev-env down "$env_name" --volumes
done

# Remove all dev-env networks
docker network ls | grep dev- | awk '{print $2}' | while read network; do
    echo "Removing network: $network"
    docker network rm "$network" 2>/dev/null || true
done

echo "Emergency shutdown complete"
```

This security model provides comprehensive protection while maintaining development productivity. For implementation details, see the [API Reference](api-reference.md).