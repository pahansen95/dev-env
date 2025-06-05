# Context System

A Context represents an isolated development workspace that maintains configuration, runtime state, and data across sessions. Contexts provide a project-centric approach to development environment management, enabling developers to quickly switch between projects without manual setup or cleanup.

## Core Concepts

Contexts encapsulate three primary components:

- **Configuration**: Runtime settings, tool versions, and service definitions
- **State**: Container runtime, filesystem modifications, and process information
- **Data**: Persistent volumes, workspace files, and user preferences

## Context Resolution

Dev-env automatically discovers contexts through hierarchical filesystem traversal:

```
current_directory/.dev-env/
parent_directory/.dev-env/
~/projects/webapp/.dev-env/
~/.dev-env/contexts/
```

Resolution follows a deterministic path, checking each directory level until finding a `.dev-env/` marker directory or reaching the filesystem root.

## Context Lifecycle

Contexts transition through defined states:

- **Active**: Running and accessible for development work
- **Suspended**: Stopped with preserved state for quick resumption
- **Archived**: Long-term storage with compressed state data

State transitions preserve developer work, ensuring no data loss between sessions.

## Directory Structure

Each context maintains a consistent filesystem layout:

```
.dev-env/
├── context.yaml      # Context metadata
├── config.yaml       # Environment configuration
├── state/           # Runtime state information
└── data/            # Persistent data storage
```

This structure enables version control integration and team collaboration through shared configurations.

## Usage Patterns

### Project-Based Development

Navigate to any project directory and start working:

```bash
cd ~/projects/webapp
dev-env work
```

Dev-env creates or resumes the appropriate context based on the current directory.

### Named Contexts

Create standalone contexts for specific tasks:

```bash
dev-env work debug-tools
```

Named contexts reside in `~/.dev-env/contexts/` for global accessibility.

## Configuration

Contexts support multiple configuration formats:

- `.devcontainer/devcontainer.json` - VS Code Dev Container format
- `dev-env.yaml` - Native dev-env configuration
- `docker-compose.yaml` - Docker Compose compatibility
- Auto-detection from project files

Configuration precedence follows the order listed, with auto-detection as the final fallback.