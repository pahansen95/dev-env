# Dev-Env Refactoring Implementation Plan

## Overview

This plan details the specific tasks required to streamline the dev-env codebase, reducing complexity by 30-40% while maintaining all user-facing functionality.

## Task Categories

### 1. Configuration System Refactoring [Priority: HIGH]

#### Task 1.1: Remove JSON Configuration Support
**Effort**: 2 hours  
**Dependencies**: None  
**Files Modified**: `src/dev_env/config.py`, `src/dev_env/cli.py`

**Implementation**:
- Remove JSON parsing logic from `load_environment()`
- Delete `Environment.from_dict()` method
- Update CLI to accept only `.py` files
- Remove JSON-related tests

**Acceptance Criteria**:
- Only Python configuration files are supported
- All JSON examples removed from documentation
- Tests pass without JSON fixtures

#### Task 1.2: Flatten Security Configuration
**Effort**: 3 hours  
**Dependencies**: Task 1.1  
**Files Modified**: `src/dev_env/config.py`, `src/dev_env/docker.py`

**Implementation**:
```python
@dataclass
class Environment:
    name: str
    base_image: str
    command: list[str] | None = None
    
    # Security fields (formerly SecurityConfig)
    user: str = "1000:1000"
    drop_capabilities: list[str] = field(default_factory=lambda: ["ALL"])
    add_capabilities: list[str] = field(default_factory=list)
    no_new_privileges: bool = True
    
    # Resource fields (formerly ResourceConfig)
    memory: str = "2g"
    cpus: float = 2.0
    pids_limit: int = 1000
```

**Acceptance Criteria**:
- SecurityConfig and ResourceConfig classes removed
- All security/resource fields directly on Environment
- Docker client updated to use flat structure

#### Task 1.3: Simplify Volume Configuration
**Effort**: 2 hours  
**Dependencies**: Task 1.2  
**Files Modified**: `src/dev_env/config.py`

**Implementation**:
- Remove VolumeMount.type field (infer from source path)
- Remove redundant validation in `__post_init__`
- Simplify volume creation logic

**Acceptance Criteria**:
- Volume type automatically detected
- Simplified volume handling in Docker client

### 2. Docker Client Streamlining [Priority: HIGH]

#### Task 2.1: Consolidate Exec Methods
**Effort**: 2 hours  
**Dependencies**: None  
**Files Modified**: `src/dev_env/docker.py`

**Implementation**:
- Merge `create_exec`, `start_exec`, `get_exec_info` into single `exec_run`
- Remove intermediate exec tracking
- Simplify return type to `(output: bytes, exit_code: int)`

**Acceptance Criteria**:
- Single exec method handles all use cases
- Simplified error handling
- Tests updated for new API

#### Task 2.2: Remove Auxiliary Features
**Effort**: 1 hour  
**Dependencies**: Task 2.1  
**Files Modified**: `src/dev_env/docker.py`, `src/dev_env/cli.py`

**Implementation**:
- Remove `get_volume_usage()` method
- Remove `attach_container()` method
- Remove network listing/inspection methods
- Update CLI to remove dependent features

**Acceptance Criteria**:
- Reduced Docker client API surface
- CLI commands still functional without removed features

#### Task 2.3: Simplify Error Handling
**Effort**: 2 hours  
**Dependencies**: Task 2.2  
**Files Modified**: `src/dev_env/docker.py`, `src/dev_env/utils.py`

**Implementation**:
- Create single `DockerError` exception class
- Remove method-specific error handling
- Use pattern matching for error classification

**Acceptance Criteria**:
- Consistent error messages
- Simplified exception hierarchy
- Clear error remediation

### 3. State Management Simplification [Priority: MEDIUM]

#### Task 3.1: Simplify Database Schema
**Effort**: 3 hours  
**Dependencies**: None  
**Files Modified**: `src/dev_env/state.py`

**Implementation**:
```python
# New simplified schema
CREATE TABLE environments (
    name TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    config JSON NOT NULL,
    created_at TEXT NOT NULL
)
```

**Acceptance Criteria**:
- Single table design
- JSON storage for complex data
- Migration handled automatically

#### Task 3.2: Remove Metadata Support
**Effort**: 1 hour  
**Dependencies**: Task 3.1  
**Files Modified**: `src/dev_env/state.py`

**Implementation**:
- Remove metadata table
- Remove get/set metadata methods
- Inline any essential metadata into environment table

**Acceptance Criteria**:
- No metadata functionality
- Essential data preserved in main table

### 4. Python 3.13 Modernization [Priority: HIGH]

#### Task 4.1: Update Type Annotations
**Effort**: 2 hours  
**Dependencies**: None  
**Files Modified**: All Python files

**Implementation**:
- Replace `Optional[T]` with `T | None`
- Replace `List[T]` with `list[T]`
- Replace `Dict[K, V]` with `dict[K, V]`
- Remove `from typing import` statements where possible

**Acceptance Criteria**:
- Modern type syntax throughout
- Type checker passes

#### Task 4.2: Implement Pattern Matching
**Effort**: 3 hours  
**Dependencies**: Task 4.1  
**Files Modified**: `src/dev_env/cli.py`, `src/dev_env/docker.py`

**Implementation**:
```python
# Example: Replace command dispatch
match args.command:
    case "up":
        return cmd_up(args)
    case "down":
        return cmd_down(args)
    case "exec":
        return cmd_exec(args)
    case _:
        parser.print_help()
        return 1
```

**Acceptance Criteria**:
- Complex if/elif chains replaced
- Cleaner error handling
- Improved readability

#### Task 4.3: Pathlib Migration
**Effort**: 2 hours  
**Dependencies**: None  
**Files Modified**: All files using file operations

**Implementation**:
- Replace all `os.path` operations
- Use Path methods for file I/O
- Remove string path manipulation

**Acceptance Criteria**:
- No `os.path` imports
- Consistent Path usage

### 5. Utility Consolidation [Priority: MEDIUM]

#### Task 5.1: Merge SSH/Git Utilities
**Effort**: 2 hours  
**Dependencies**: None  
**Files Modified**: `src/dev_env/utils.py`

**Implementation**:
- Create single `setup_development_tools()` function
- Combine SSH and Git installation logic
- Reduce redundant subprocess calls

**Acceptance Criteria**:
- Single function for dev tool setup
- Simplified error handling
- Maintained functionality

#### Task 5.2: Reduce Error Classes
**Effort**: 2 hours  
**Dependencies**: Task 2.3  
**Files Modified**: `src/dev_env/utils.py`

**Implementation**:
```python
class DevEnvError(Exception):
    """Base error with remediation"""
    def __init__(self, message: str, remediation: str = ""):
        self.message = message
        self.remediation = remediation

class ConfigError(DevEnvError):
    """Configuration-related errors"""
    pass

class DockerError(DevEnvError):
    """Docker operation errors"""
    pass
```

**Acceptance Criteria**:
- Maximum 3 error classes
- Clear error hierarchy
- Consistent remediation messages

### 6. Test Suite Refactoring [Priority: HIGH]

#### Task 6.1: Consolidate Test Files
**Effort**: 4 hours  
**Dependencies**: Tasks 1-5 complete  
**Files Modified**: All test files

**Implementation**:
- Merge related test modules
- Remove redundant test cases
- Focus on integration tests

**Target Structure**:
```
tests/
  test_core.py      # Config, state, docker
  test_cli.py       # CLI commands
  test_integration.py # Full workflows
```

**Acceptance Criteria**:
- 50% fewer test files
- Maintained coverage
- Faster test execution

#### Task 6.2: Simplify Fixtures
**Effort**: 3 hours  
**Dependencies**: Task 6.1  
**Files Modified**: `tests/conftest.py`

**Implementation**:
- Create single `mock_environment` fixture
- Remove granular mock fixtures
- Use real objects where possible

**Acceptance Criteria**:
- Simplified fixture hierarchy
- Reduced mock complexity
- Clearer test setup

#### Task 6.3: Remove Implementation Tests
**Effort**: 2 hours  
**Dependencies**: Task 6.2  
**Files Modified**: All test files

**Implementation**:
- Remove tests for private methods
- Remove defensive edge case tests
- Focus on user-facing behavior

**Acceptance Criteria**:
- Only public API tested
- Behavioral focus
- Maintained 85% coverage

### 7. Documentation Updates [Priority: LOW]

#### Task 7.1: Remove JSON Examples
**Effort**: 1 hour  
**Dependencies**: Task 1.1  
**Files Modified**: All documentation

**Implementation**:
- Remove JSON configuration examples
- Update user guide
- Simplify quickstart

**Acceptance Criteria**:
- No JSON references
- Python-only examples

#### Task 7.2: Update Architecture Documentation
**Effort**: 2 hours  
**Dependencies**: All tasks complete  
**Files Modified**: `docs/design.md`, `README.md`

**Implementation**:
- Reflect simplified architecture
- Update component descriptions
- Remove obsolete features

**Acceptance Criteria**:
- Accurate architecture description
- Updated diagrams
- Clear design rationale

## Execution Order

### Week 1: Core Refactoring
1. Task 1.1: Remove JSON Configuration (Day 1)
2. Task 1.2: Flatten Security Configuration (Day 1)
3. Task 1.3: Simplify Volume Configuration (Day 2)
4. Task 4.1: Update Type Annotations (Day 2)
5. Task 4.2: Implement Pattern Matching (Day 3)
6. Task 4.3: Pathlib Migration (Day 3)
7. Task 2.1: Consolidate Exec Methods (Day 4)
8. Task 2.2: Remove Auxiliary Features (Day 4)
9. Task 2.3: Simplify Error Handling (Day 5)

### Week 2: Consolidation and Testing
1. Task 3.1: Simplify Database Schema (Day 1)
2. Task 3.2: Remove Metadata Support (Day 1)
3. Task 5.1: Merge SSH/Git Utilities (Day 2)
4. Task 5.2: Reduce Error Classes (Day 2)
5. Task 6.1: Consolidate Test Files (Day 3)
6. Task 6.2: Simplify Fixtures (Day 4)
7. Task 6.3: Remove Implementation Tests (Day 4)
8. Task 7.1: Remove JSON Examples (Day 5)
9. Task 7.2: Update Architecture Documentation (Day 5)

## Success Metrics

- **Code Reduction**: 30-40% fewer lines of code
- **Test Performance**: 50% faster test execution
- **API Surface**: 40% fewer public methods
- **Complexity**: 60% reduction in cyclomatic complexity
- **Dependencies**: Maintained at zero external dependencies

## Risk Mitigation

### Backward Compatibility
- Create migration guide for users
- Tag current version before changes
- Document all breaking changes

### Feature Regression
- Maintain comprehensive integration tests
- Manual testing of all workflows
- User acceptance testing

### Performance Impact
- Benchmark before/after changes
- Profile critical paths
- Optimize bottlenecks if found