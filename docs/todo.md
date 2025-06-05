# Context & CLI Implementation Plan

## Overview

This plan implements a context-based development environment system with porcelain (user-friendly) and plumbing (low-level) CLI commands. The implementation follows a phased approach to ensure incremental delivery and testing.

## Phase 1: Context Foundation (Week 1)

### Objective
Implement the core context system for managing isolated development workspaces.

### Deliverables

#### 1.1 Context Data Model
Create `src/dev_env/context.py`:

```python
@dataclass
class Context:
    """Represents an isolated development workspace"""
    id: str          # SHA-256 hash of name + path
    name: str        # Human-readable identifier
    path: Path       # Filesystem location
    created_at: str  # ISO timestamp
    last_used: str   # ISO timestamp
    state: str       # active|suspended|archived
```

#### 1.2 Context Resolution
Implement `src/dev_env/context_resolver.py`:

```python
class ContextResolver:
    def resolve(self, name: Optional[str] = None) -> Optional[Context]:
        """
        Resolution order:
        1. If name provided, check registry
        2. Walk up from cwd looking for .dev-env/
        3. Return None if not found
        """
```

#### 1.3 Context Storage
Extend `src/dev_env/state.py`:

```python
class ContextManager(StateManager):
    def create_context(self, name: str, path: Path) -> Context
    def get_context(self, context_id: str) -> Optional[Context]
    def list_contexts(self) -> List[Context]
    def update_context(self, context: Context) -> None
```

### Implementation Notes
- Use SQLite for context registry (extend existing state.db)
- Context ID = SHA-256(name + absolute_path)
- Store contexts table with indexed lookups

### Testing Requirements
- Unit tests for context creation, resolution, and storage
- Test hierarchical directory resolution
- Test registry persistence

## Phase 2: Plumbing Commands (Week 2)

### Objective
Implement low-level commands that output JSON and compose well.

### Deliverables

#### 2.1 Base Plumbing Command
Create `src/dev_env/cli_plumbing.py`:

```python
class PlumbingCommand:
    """Base class for all plumbing commands"""
    
    def execute(self, args) -> dict:
        """Returns JSON-serializable dict"""
        raise NotImplementedError
    
    def output(self, result: dict) -> None:
        """Outputs JSON to stdout"""
        print(json.dumps(result))
```

#### 2.2 Context Plumbing Commands
Implement in `src/dev_env/commands/plumbing/`:

- `context_create.py` - Creates new context
- `context_resolve.py` - Resolves context from path/name
- `context_list.py` - Lists all contexts

#### 2.3 Environment Plumbing Commands
Implement core lifecycle commands:

- `env_create.py` - Creates container from config
- `env_start.py` - Starts existing container
- `env_stop.py` - Stops running container
- `env_status.py` - Returns current state

#### 2.4 Execution Plumbing
- `exec.py` - Executes command in container
- `attach.py` - Attaches to container TTY

### Implementation Guidelines

Command Structure:
```python
# commands/plumbing/context_resolve.py
class ContextResolveCommand(PlumbingCommand):
    def execute(self, args):
        resolver = ContextResolver()
        context = resolver.resolve(args.name)
        
        if not context:
            return {"error": "Context not found", "code": "CONTEXT_NOT_FOUND"}
        
        return {
            "id": context.id,
            "name": context.name,
            "path": str(context.path)
        }
```

CLI Integration:
```python
# Add to cli.py
plumbing_parser = subparsers.add_parser('context-resolve')
plumbing_parser.set_defaults(func=lambda args: ContextResolveCommand().execute(args))
```

### Testing Requirements
- Test JSON output format
- Test error conditions
- Test command composition with pipes

## Phase 3: Porcelain Commands (Week 3)

### Objective
Implement user-friendly commands that orchestrate plumbing commands.

### Deliverables

#### 3.1 Work Command
Create `src/dev_env/commands/porcelain/work.py`:

```python
class WorkCommand:
    def execute(self, args):
        # 1. Resolve or create context
        # 2. Load or generate config
        # 3. Create or start environment
        # 4. Show progress and status
```

#### 3.2 Core Porcelain Commands
- `stop.py` - Suspends current/named environment
- `run.py` - Executes command in current context
- `status.py` - Shows human-readable status
- `shell.py` - Opens interactive shell

### Implementation Pattern

```python
# commands/porcelain/work.py
class WorkCommand:
    def execute(self, args):
        # Step 1: Context resolution
        context = self._resolve_context(args.name)
        if not context:
            context = self._create_context()
        
        # Step 2: Configuration
        config = self._load_config(context)
        if not config:
            config = self._setup_wizard()
        
        # Step 3: Environment management
        status = self._get_status(context)
        if status['state'] == 'stopped':
            self._start_environment(context)
        elif status['state'] == 'notfound':
            self._create_environment(context, config)
        
        # Step 4: User feedback
        self._show_ready_message(context)
    
    def _run_plumbing(self, command: str, *args) -> dict:
        """Helper to run plumbing commands"""
        # Implementation detail
```

### Progress Feedback
Use `rich` library patterns (without importing):

```python
def _show_progress(self, message: str, done: bool = False):
    symbol = "✓" if done else "●"
    print(f"{symbol} {message}")
```

### Testing Requirements
- Integration tests for full workflows
- Mock plumbing commands for unit tests
- Test user feedback and error messages

## Phase 4: Configuration & Setup Wizard (Week 4)

### Objective
Implement configuration detection and interactive setup.

### Deliverables

#### 4.1 Configuration Detection
Create `src/dev_env/config_detector.py`:

```python
class ConfigDetector:
    def detect(self, path: Path) -> Optional[dict]:
        """
        Detection order:
        1. .devcontainer/devcontainer.json
        2. dev-env.yaml
        3. docker-compose.yaml
        4. Dockerfile
        5. Language-specific files (package.json, requirements.txt)
        """
```

#### 4.2 Setup Wizard
Create `src/dev_env/setup_wizard.py`:

```python
class SetupWizard:
    def run(self, context: Context) -> dict:
        """Interactive configuration generation"""
        # 1. Detect project type
        # 2. Ask minimal questions
        # 3. Generate configuration
        # 4. Save to context path
```

### Testing Requirements
- Test detection for various project types
- Test wizard flow with mocked input
- Test configuration generation

## Phase 5: Integration & Polish (Week 5)

### Objective
Integrate all components and add polish features.

### Deliverables

#### 5.1 State Preservation
- Implement filesystem overlay tracking
- Add volume state management
- Create snapshot/restore functionality

#### 5.2 Error Handling
Implement consistent error handling:

```python
class DevEnvError(Exception):
    def to_json(self) -> dict:
        return {
            "error": self.message,
            "code": self.code,
            "remediation": self.remediation
        }
```

#### 5.3 Shell Completion
Update `src/dev_env/completion.py`:
- Add context name completion
- Add command suggestions
- Support new command structure

### Testing Requirements
- End-to-end workflow tests
- Performance benchmarks
- User acceptance testing

## Implementation Guidelines

### Code Organization
```
src/dev_env/
├── context.py              # Context data model
├── context_resolver.py     # Resolution logic
├── config_detector.py      # Configuration detection
├── setup_wizard.py         # Interactive setup
├── commands/
│   ├── porcelain/         # User-facing commands
│   │   ├── work.py
│   │   ├── stop.py
│   │   ├── run.py
│   │   ├── status.py
│   │   └── shell.py
│   └── plumbing/          # Low-level commands
│       ├── context_*.py
│       ├── env_*.py
│       └── exec.py
└── cli.py                  # Updated CLI entry point
```

### Testing Strategy
1. Unit tests for each module
2. Integration tests for command workflows
3. Mock Docker operations for speed
4. Real Docker tests marked as `@pytest.mark.slow`

### Migration Path
1. Keep existing commands working
2. Add deprecation warnings after Phase 3
3. Update documentation incrementally
4. Provide migration guide

## Success Criteria

### Functionality
- [ ] Context resolution works from any subdirectory
- [ ] Porcelain commands complete in <5 seconds
- [ ] Plumbing commands output valid JSON
- [ ] Setup wizard generates working configs
- [ ] State persists between sessions

### User Experience
- [ ] Single command to start working
- [ ] Clear progress feedback
- [ ] Actionable error messages
- [ ] Intuitive command structure
- [ ] Fast context switching

### Code Quality
- [ ] 90%+ test coverage
- [ ] Type hints throughout
- [ ] Comprehensive docstrings
- [ ] No external dependencies
- [ ] Clean separation of concerns