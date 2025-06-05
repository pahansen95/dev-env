# Plumbing Commands

Plumbing commands provide low-level operations that output machine-readable JSON. These commands follow Unix philosophy principles: do one thing well, compose through pipes, and never require interactive input.

## Design Principles

- **Machine-Readable Output**: All commands output valid JSON
- **Composability**: Commands work together through standard pipes
- **Deterministic Behavior**: Same inputs produce same outputs
- **Exit Code Semantics**: Non-zero codes indicate specific error conditions

## Context Operations

### `dev-env context-create <name> <path>`

Creates a new context at the specified filesystem location.

**Usage:**
```bash
dev-env context-create webapp ./
```

**Output:**
```json
{
  "id": "abc123def456",
  "name": "webapp",
  "path": "/home/user/projects/webapp/.dev-env"
}
```

### `dev-env context-resolve [name]`

Resolves a context from the current directory or by name.

**Usage:**
```bash
dev-env context-resolve          # From current directory
dev-env context-resolve webapp   # By name
```

**Output:**
```json
{
  "id": "abc123def456",
  "name": "webapp",
  "path": "/home/user/projects/webapp/.dev-env"
}
```

### `dev-env context-list`

Lists all known contexts in the registry.

**Usage:**
```bash
dev-env context-list
```

**Output:**
```json
[
  {
    "id": "abc123def456",
    "name": "webapp",
    "state": "active"
  }
]
```

## Environment Operations

### `dev-env env-create <context-id> <config-path>`

Creates an environment container from configuration.

**Usage:**
```bash
dev-env env-create abc123def456 ./config.yaml
```

**Output:**
```json
{
  "container_id": "container789xyz",
  "state": "created"
}
```

### `dev-env env-start <context-id>`

Starts an existing environment container.

**Usage:**
```bash
dev-env env-start abc123def456
```

**Output:**
```json
{
  "container_id": "container789xyz",
  "state": "running"
}
```

### `dev-env env-stop <context-id>`

Stops a running environment container.

**Usage:**
```bash
dev-env env-stop abc123def456
```

**Output:**
```json
{
  "container_id": "container789xyz",
  "state": "stopped"
}
```

### `dev-env env-status <context-id>`

Returns current environment state and resource usage.

**Usage:**
```bash
dev-env env-status abc123def456
```

**Output:**
```json
{
  "state": "running",
  "container_id": "container789xyz",
  "resources": {
    "cpu_percent": 12.5,
    "memory_mb": 512
  }
}
```

## Execution Operations

### `dev-env exec <context-id> -- <command> [args...]`

Executes a command within the environment.

**Usage:**
```bash
dev-env exec abc123def456 -- python --version
```

**Output:**
```
Python 3.13.0
```

**Exit Code**: Propagates from executed command

### `dev-env attach <context-id> [--tty]`

Attaches to the environment's primary process.

**Usage:**
```bash
dev-env attach abc123def456 --tty
```

**Behavior**: Direct terminal attachment, no JSON output

## Configuration Operations

### `dev-env config-load <path>`

Loads and validates configuration files.

**Usage:**
```bash
dev-env config-load ./dev-env.yaml
```

**Output:**
```json
{
  "valid": true,
  "config": {
    "image": "python:3.13",
    "ports": [8080]
  }
}
```

## Error Handling

All plumbing commands return consistent error structures:

```json
{
  "error": "Context not found",
  "code": "CONTEXT_NOT_FOUND",
  "details": {}
}
```

## Composition Patterns

Plumbing commands compose through standard Unix pipes:

```bash
# Stop all running environments
dev-env context-list | \
  jq -r '.[] | select(.state == "running") | .id' | \
  xargs -I{} dev-env env-stop {}

# Get total memory usage
dev-env context-list | \
  jq -r '.[].id' | \
  xargs -I{} dev-env env-status {} | \
  jq -s 'map(.resources.memory_mb) | add'
```

## Implementation Notes

Plumbing commands map directly to internal API functions, providing a stable interface for automation and scripting. They deliberately expose minimal functionality to maintain simplicity and composability.