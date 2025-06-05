# Porcelain Commands

Porcelain commands provide high-level, user-friendly operations for managing development environments. These commands handle complex workflows internally while presenting simple interfaces optimized for developer productivity.

## Primary Commands

### `dev-env work [name]`

Starts or resumes development work in a context. This command handles all environment lifecycle operations automatically.

**Usage:**
```bash
dev-env work              # Use current directory's context
dev-env work webapp       # Use named context
```

**Behavior:**
- Creates context if none exists
- Starts stopped environments
- Resumes suspended state
- Shows progress feedback

### `dev-env stop [name] [--all]`

Suspends active development environments while preserving state.

**Usage:**
```bash
dev-env stop              # Stop current context
dev-env stop webapp       # Stop specific context
dev-env stop --all        # Stop all contexts
```

**State Preservation:**
- Filesystem modifications retained
- Running processes gracefully terminated
- Data volumes preserved

### `dev-env run <command> [...args]`

Executes commands within the active context environment.

**Usage:**
```bash
dev-env run python script.py
dev-env run npm install
dev-env run --env webapp pytest
```

**Features:**
- Automatic context detection
- Exit code preservation
- Standard I/O passthrough

### `dev-env shell [name]`

Opens an interactive shell session in the context environment.

**Usage:**
```bash
dev-env shell             # Current context
dev-env shell webapp      # Specific context
```

**Shell Detection:**
- Prefers bash if available
- Falls back to sh
- Preserves terminal settings

### `dev-env status [--all]`

Displays context and environment status information.

**Usage:**
```bash
dev-env status            # Current context
dev-env status --all      # All contexts
```

**Information Displayed:**
- Context state (active/suspended)
- Resource utilization
- Service endpoints
- Uptime statistics

## Secondary Commands

### `dev-env clean`

Removes stopped environments and frees resources.

**Interactive Mode:**
Shows candidates for removal with size information, allowing selective cleanup.

### `dev-env config`

Configuration management utilities.

**Subcommands:**
- `init` - Initialize new configuration
- `show` - Display active configuration
- `validate` - Check configuration validity

## Command Patterns

### Context Awareness

Commands automatically detect the current context from the working directory, reducing the need for explicit context specification.

### Idempotent Operations

Commands like `work` are idempotent - running them multiple times produces the same result without errors.

### Progress Feedback

All long-running operations provide real-time progress indicators with time estimates.

## Exit Codes

Porcelain commands use consistent exit codes:

- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Context not found
- `4` - Operation failed