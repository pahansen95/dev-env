# Architecture Overview

This document describes the system architecture of dev-env, including design principles, component relationships, and key architectural decisions.

## Design Principles

Dev-env is built on five core principles that guide all architectural decisions:

### 1. Zero Dependencies

**Principle**: Use only Python standard library - no external packages.

**Rationale**:
- Eliminates dependency conflicts
- Simplifies installation and distribution
- Reduces security attack surface
- Ensures long-term stability

**Implementation**:
- Docker API client using `http.client` and Unix sockets
- SQLite for state management (included in Python)
- Configuration using dataclasses (stdlib)
- CLI using argparse (stdlib)

### 2. Simplicity First

**Principle**: Choose the simplest solution that solves the problem.

**Rationale**:
- Easier to understand and maintain
- Reduces bugs and edge cases
- Improves reliability

**Implementation**:
- Direct Docker API usage instead of abstraction layers
- Python files for configuration instead of YAML/JSON
- Simple SQLite schema for state tracking
- Minimal CLI commands with clear purposes

### 3. Developer Experience

**Principle**: Optimize for developer productivity and intuition.

**Rationale**:
- Developers should focus on code, not infrastructure
- Common tasks should be effortless
- Error messages should be helpful

**Implementation**:
- Automatic SSH configuration
- Git repository cloning on startup
- Intelligent error messages with solutions
- Shell completion support

### 4. Secure by Default

**Principle**: Security should not be optional or require configuration.

**Rationale**:
- Prevents accidental security vulnerabilities
- Protects both host and container environments
- Builds security awareness

**Implementation**:
- Non-root container execution
- Localhost-only port binding
- Forbidden system mount paths
- SSH key-based authentication only

### 5. Explicit Configuration

**Principle**: Configuration should be code with type safety.

**Rationale**:
- Catches errors at configuration time
- Enables IDE support and autocompletion
- Allows dynamic configuration
- Self-documenting through types

**Implementation**:
- Python dataclasses for configuration
- Type hints throughout
- Validation in constructors
- No implicit defaults for security-sensitive settings

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                         User Layer                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │     CLI     │  │ Python Config│  │ Shell Completion│   │
│  │  (argparse) │  │    Files     │  │    Scripts      │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                  │
├─────────────────────────────────────────────────────────────┤
│                    Application Layer                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Config    │  │    State     │  │     Utils       │   │
│  │   System    │  │   Manager    │  │   Functions     │   │
│  │(dataclasses)│  │   (SQLite)   │  │  (validation)   │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬────────┘   │
│         │                │                    │             │
│         └────────────────┼────────────────────┘             │
│                          ▼                                  │
├─────────────────────────────────────────────────────────────┤
│                     Docker Layer                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Docker Client                        │  │
│  │  (Unix Socket HTTP Client - Zero Dependencies)       │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│                         ▼                                   │
├─────────────────────────────────────────────────────────────┤
│                   Infrastructure                             │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │   Docker    │  │  File System │  │    Network      │   │
│  │   Daemon    │  │   (volumes)  │  │   (bridges)     │   │
│  └─────────────┘  └──────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Interactions

```
User → CLI → Config Loader → Docker Client → Container
       ↓          ↓              ↓
    State     Validation    SSH Setup
    Manager                     ↓
       ↓                   Git Clone
    SQLite DB
```

## Core Components

### 1. CLI Layer (`cli.py`)

**Purpose**: User interface for all operations

**Responsibilities**:
- Parse command-line arguments
- Load and validate configurations
- Orchestrate operations
- Display results and errors

**Key Design Decisions**:
- Subcommand-based interface (up, down, list, etc.)
- Consistent error handling and exit codes
- Progress feedback for long operations

### 2. Configuration System (`config.py`)

**Purpose**: Type-safe environment definitions

**Responsibilities**:
- Define environment structure
- Validate configuration values
- Apply security defaults
- Convert to Docker API format

**Key Design Decisions**:
- Dataclasses for type safety
- Validation in `__post_init__`
- Immutable after creation
- Composable components (GitConfig, SSHConfig, etc.)

### 3. Docker Client (`docker.py`)

**Purpose**: Communicate with Docker daemon

**Responsibilities**:
- HTTP over Unix socket communication
- Docker API request/response handling
- Container lifecycle management
- Image and volume operations

**Key Design Decisions**:
- No external Docker libraries
- Minimal API surface (only needed endpoints)
- Direct JSON manipulation
- Explicit error handling

### 4. State Manager (`state.py`)

**Purpose**: Track environment state persistently

**Responsibilities**:
- Store environment metadata
- Track container associations
- Manage volume relationships
- Clean up orphaned state

**Key Design Decisions**:
- SQLite for reliability
- Simple schema design
- Transactional updates
- Automatic migrations

### 5. Utilities (`utils.py`)

**Purpose**: Shared functionality and validation

**Responsibilities**:
- Security validation
- SSH key management
- Container name generation
- Error types and formatting

**Key Design Decisions**:
- Pure functions where possible
- Comprehensive validation
- Clear error messages
- Security-first approach

## Data Flow

### Environment Creation Flow

```
1. User executes: dev-env up config.py
                        ↓
2. CLI loads configuration file
   - Import Python module
   - Extract Environment object
   - Validate configuration
                        ↓
3. Apply security defaults
   - Set non-root user
   - Validate mount paths
   - Check port bindings
                        ↓
4. Create container
   - Generate unique name
   - Pull image if needed
   - Create with configuration
                        ↓
5. Initialize container
   - Setup SSH if configured
   - Clone git repository
   - Start services
                        ↓
6. Save state
   - Record container ID
   - Save configuration
   - Track volumes
                        ↓
7. Report success
   - Display connection info
   - Show next steps
```

### State Management Flow

```
State Manager
     │
     ├── Save Environment
     │   ├── Container ID
     │   ├── Configuration
     │   ├── Volume Names
     │   └── Timestamps
     │
     ├── Load Environment
     │   ├── Query by name
     │   ├── Deserialize config
     │   └── Return state
     │
     └── Track Lifecycle
         ├── Creation time
         ├── Last accessed
         └── Deletion cleanup
```

## Security Architecture

### Container Security

```
Container
    │
    ├── User Context
    │   ├── Non-root (1000:1000)
    │   ├── Home directory
    │   └── Limited sudo
    │
    ├── Capabilities
    │   ├── Drop ALL by default
    │   ├── Add only required
    │   └── No new privileges
    │
    └── Filesystem
        ├── Read-only option
        ├── Protected mounts
        └── Named volumes
```

### Network Security

```
Network Isolation
    │
    ├── Port Binding
    │   ├── Localhost only (127.0.0.1)
    │   ├── Explicit external binding
    │   └── Privileged port protection
    │
    ├── Network Drivers
    │   ├── Bridge (isolated)
    │   ├── Internal (no external)
    │   └── Custom networks
    │
    └── SSH Access
        ├── Key-based only
        ├── No root login
        └── Authorized keys
```

## Performance Considerations

### Startup Optimization

1. **Image Caching**: Pre-pulled base images
2. **Shallow Clones**: Git repositories with `--depth 1`
3. **Parallel Operations**: Concurrent volume creation
4. **Lazy Initialization**: SSH setup only when needed

### Resource Management

1. **Container Limits**: Memory and CPU constraints
2. **Volume Cleanup**: Automatic orphan detection
3. **State Pruning**: Remove old environment records
4. **Connection Pooling**: Reuse Docker client connections

## Error Handling Strategy

### Error Categories

```
DevEnvError (Base)
    │
    ├── ConfigError
    │   ├── Invalid configuration
    │   ├── Missing required fields
    │   └── Security violations
    │
    ├── DockerError
    │   ├── Daemon unavailable
    │   ├── Container operations
    │   └── Network conflicts
    │
    └── StateError
        ├── Corruption
        ├── Lock timeout
        └── Migration failure
```

### Error Response Pattern

```python
try:
    # Operation
except SpecificError as e:
    # Log detailed error
    logger.error(f"Operation failed: {e}", extra=context)
    
    # User-friendly message
    print(e.format_error(), file=sys.stderr)
    
    # Cleanup if needed
    cleanup_partial_state()
    
    # Exit with specific code
    return e.exit_code
```

## Extension Points

### 1. Custom Base Images

- Build specialized development images
- Pre-install language tools
- Configure development users

### 2. Configuration Templates

- Language-specific defaults
- Project type patterns
- Team standards

### 3. Lifecycle Hooks

- Pre/post creation scripts
- Environment initialization
- Cleanup procedures

### 4. Network Architectures

- Multi-service meshes
- Load balancer integration
- Service discovery

## Future Architecture Considerations

### Potential Enhancements

1. **Plugin System**: Dynamic loading of extensions
2. **Remote Environments**: Cloud-based development
3. **Multi-Host**: Distributed environments
4. **State Sync**: Team environment sharing

### Maintaining Principles

Any future changes must:
- Maintain zero-dependency core
- Preserve simplicity
- Enhance developer experience
- Strengthen security
- Keep configuration explicit

## Conclusion

The dev-env architecture prioritizes simplicity, security, and developer experience while maintaining zero external dependencies. This design enables reliable, fast, and secure development environment management with minimal complexity.

For implementation details of specific components, see:
- [Docker Client Implementation](docker-client.md)
- [State Management Design](state-management.md)
- [Container Lifecycle](container-lifecycle.md)