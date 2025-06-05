# Migration Guide: Legacy to Context-Based Commands

## Overview

This guide provides a systematic approach for migrating from legacy dev-env commands to the modern context-based interface. The migration eliminates manual environment tracking while introducing automatic workspace detection and intelligent configuration management.

## Command Migration Reference

### Direct Command Mappings

| Legacy Command | Modern Equivalent | Key Changes |
|----------------|-------------------|-------------|
| `dev-env up config.py` | `dev-env work` | Auto-detects context, YAML configuration |
| `dev-env down name` | `dev-env stop` | Context-aware operation |
| `dev-env list` | `dev-env status --all` | Rich formatting with timestamps |
| `dev-env exec name cmd` | `dev-env run cmd` | Auto-resolves current context |
| `dev-env ssh name` | `dev-env shell` | Interactive shell access |
| `dev-env logs name` | `dev-env status` | Integrated log viewing |

### Workflow Transformation

**Legacy Workflow:**
```bash
# Manual environment specification required
dev-env up project-config.py --name myproject
dev-env ssh myproject
dev-env exec myproject python manage.py runserver
dev-env down myproject
```

**Modern Workflow:**
```bash
# Context-aware operation
cd /path/to/project
dev-env work
dev-env shell
dev-env run python manage.py runserver
dev-env stop
```

## Configuration Migration

### Format Conversion

**Legacy Python Configuration:**
```python
from dev_env.config import Environment, VolumeMount, GitConfig

environment = Environment(
    name="django-app",
    base_image="python:3.13",
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "DJANGO_SETTINGS_MODULE": "myproject.settings.dev",
        "PYTHONUNBUFFERED": "1"
    },
    git=GitConfig(
        url="git@github.com:user/django-app.git",
        branch="main"
    )
)
```

**Modern YAML Configuration:**
```yaml
# dev-env.yaml
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
  DJANGO_SETTINGS_MODULE: myproject.settings.dev
  PYTHONUNBUFFERED: "1"
git:
  url: git@github.com:user/django-app.git
  branch: main
working_directory: /app
```

### Configuration Generation

Instead of manual conversion, use the interactive setup wizard:

```bash
cd /path/to/project
dev-env work
# Wizard automatically detects project type and generates configuration
```

## Migration Process

### Step 1: Assess Current Environments

List existing legacy environments:
```bash
# Check current environments before migration
dev-env list
```

Document active environments and their configurations for reference during migration.

### Step 2: Project Context Creation

For each project, create contexts using the modern interface:

```bash
# Navigate to project directory
cd /path/to/project

# Create context and generate configuration
dev-env work

# The wizard will:
# - Detect project type
# - Generate appropriate configuration
# - Create development context
# - Start environment
```

### Step 3: Configuration Validation

Verify generated configurations match project requirements:

```bash
# Review generated configuration
cat dev-env.yaml

# Test environment functionality
dev-env shell
# Verify environment setup within container
dev-env stop
```

### Step 4: Workflow Adoption

Update development workflows to use context-based commands:

**Before:**
```bash
# Legacy manual tracking
dev-env up myproject.py
dev-env ssh myproject
# ... development work ...
dev-env down myproject
```

**After:**
```bash
# Context-aware workflow
cd project-directory
dev-env work
dev-env shell
# ... development work ...
dev-env stop
```

### Step 5: Legacy Cleanup

Once migration is complete, remove legacy configuration files:

```bash
# Remove Python configuration files
rm *.py  # Only configuration files, not project code

# Verify modern workflow
dev-env status --all
```

## Advanced Migration Scenarios

### Multi-Project Workflows

**Legacy Multi-Project Management:**
```bash
# Manual environment tracking
dev-env up frontend.py --name frontend
dev-env up backend.py --name backend
dev-env up database.py --name database

# Connect to specific environments
dev-env ssh frontend
dev-env ssh backend
```

**Modern Multi-Project Management:**
```bash
# Context-aware project switching
cd frontend/
dev-env work

cd ../backend/
dev-env work

cd ../database/
dev-env work

# View all active contexts
dev-env status --all
```

### Complex Configuration Migration

For projects with advanced configurations, manual YAML creation may be necessary:

**Legacy Complex Configuration:**
```python
environment = Environment(
    name="microservice",
    base_image="golang:1.21",
    command=["tail", "-f", "/dev/null"],
    ports={
        8080: {"HostPort": 8080},
        9090: {"HostPort": 9090}
    },
    volumes=[
        VolumeMount(source=".", target="/go/src/app"),
        VolumeMount(source="go-cache", target="/go/pkg/mod", type="named")
    ],
    environment={
        "CGO_ENABLED": "0",
        "GOOS": "linux"
    },
    network=NetworkConfig(name="microservices", driver="bridge")
)
```

**Modern YAML Equivalent:**
```yaml
base_image: golang:1.21
command: ["tail", "-f", "/dev/null"]
ports:
  - container: 8080
    host: 8080
  - container: 9090
    host: 9090
volumes:
  - source: .
    target: /go/src/app
  - source: go-cache
    target: /go/pkg/mod
    type: named
environment:
  CGO_ENABLED: "0"
  GOOS: linux
network:
  name: microservices
  driver: bridge
working_directory: /go/src/app
```

## Troubleshooting Migration Issues

### Context Resolution Problems

**Issue:** Context not found in project directory

**Solution:**
```bash
# Explicitly create context
dev-env context-create project-name --path $(pwd)

# Verify context creation
dev-env context-list
```

### Configuration Validation Errors

**Issue:** Generated YAML configuration has validation errors

**Solution:**
1. Review configuration syntax
2. Verify required fields are present
3. Check volume source paths exist
4. Ensure port availability

**Common Issues:**
- Missing `base_image` field
- Invalid YAML indentation
- Non-existent volume source paths
- Port conflicts with running services

### Legacy State Conflicts

**Issue:** Legacy environment state conflicts with new contexts

**Solution:**
```bash
# Stop all legacy environments
dev-env down environment-name

# Clean up legacy state if necessary
rm -rf ~/.dev-env/state/environments.db

# Recreate using modern interface
cd project-directory
dev-env work
```

## Validation Checklist

After migration, verify the following functionality:

- [ ] Context automatically detected in project directories
- [ ] Configuration generates correctly through wizard
- [ ] Environment starts and stops properly
- [ ] Shell access works correctly
- [ ] Port mappings function as expected
- [ ] Volume mounts preserve data
- [ ] Multiple projects can be managed simultaneously

## Benefits of Migration

### Improved Developer Experience

- **Automatic Context Detection**: No manual environment name tracking
- **Interactive Configuration**: Guided setup for new projects
- **Rich Status Display**: Enhanced environment information with timestamps
- **Simplified Commands**: Intuitive workflow without manual specification

### Enhanced Functionality

- **Project Type Detection**: Automatic configuration generation
- **Template System**: Consistent setups across similar projects
- **State Persistence**: Robust context and environment tracking
- **Error Recovery**: Clear error messages with resolution guidance

### Operational Improvements

- **Reduced Configuration Overhead**: Elimination of manual config file creation
- **Consistent Environments**: Template-based configuration ensures consistency
- **Improved Documentation**: Self-documenting YAML configuration format
- **Better Maintainability**: Structured configuration enables easier updates

## Support Resources

- **Documentation**: Complete usage documentation in `docs/user-guide.md`
- **Examples**: Configuration examples for common project types
- **Troubleshooting**: Detailed problem resolution guides
- **Community Support**: GitHub issues for migration assistance

Migration to the context-based interface provides significant improvements in developer experience while maintaining all existing functionality. The automatic context detection and guided configuration generation eliminate common setup overhead, enabling developers to focus on software development rather than environment management.
