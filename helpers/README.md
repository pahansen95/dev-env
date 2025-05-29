# Helper Scripts

This directory contains utility scripts for development and testing.

## run-tests.sh

Comprehensive test runner for the dev-env project with CI/CD support.

### Features

- **Automated environment setup** - Creates and configures Python virtual environment
- **Multiple test modes** - Unit, integration, error scenarios, or all tests
- **Coverage reporting** - HTML and XML reports with configurable thresholds
- **CI/CD ready** - JUnit XML output and strict mode for automated pipelines
- **Quality checks** - Optional linting and type checking integration
- **Parallel execution** - Support for pytest-xdist when available
- **Cleanup utilities** - Remove test artifacts and coverage files

### Usage Examples

```bash
# Run all tests with coverage (default)
./helpers/run-tests.sh

# Run only unit tests without coverage
./helpers/run-tests.sh --unit --no-coverage

# Run in CI mode with strict settings
./helpers/run-tests.sh --ci

# Setup environment only (useful for development)
./helpers/run-tests.sh --setup-only

# Clean up test artifacts
./helpers/run-tests.sh --cleanup

# Run specific tests using environment variable
PYTEST_ARGS="tests/test_simple.py::TestSimple::test_basic" ./helpers/run-tests.sh
```

### Environment Variables

- `PYTEST_ARGS` - Additional arguments passed to pytest
- `COVERAGE_MIN` - Minimum coverage threshold (default: 85)
- `CI` - Set to 'true' to automatically enable CI mode

### CI/CD Integration

The script automatically detects CI environments and enables appropriate settings:
- JUnit XML output for test results
- XML coverage reports for external tools
- Stricter error handling and validation
- Optimized output formatting

## Shared Utilities

### utils.sh

A sourceable script providing common functionality for all helper scripts:

**Logging Functions:**
- `log_info` - Information messages (blue)
- `log_success` - Success messages (green)  
- `log_warning` - Warning messages (yellow)
- `log_error` - Error messages (red)
- `log_debug` - Debug messages (purple, only shown when verbose)
- `log_progress` - Progress indicators (cyan)

**Utility Functions:**
- `command_exists` - Check if a command is available
- `get_script_dir` - Get directory of current script (works when sourced)
- `get_project_root` - Get project root directory
- `require_command` - Validate required commands exist
- `require_directory` - Validate required directories exist

**Environment Setup:**
- `setup_python_venv` - Setup Python virtual environment
- `cleanup_files` - Clean up files matching patterns

**Performance Timing:**
- `start_timer` - Start timing an operation
- `end_timer` - End timing and get duration
- `log_timer` - Log completion time

**Usage in Helper Scripts:**
```bash
#!/bin/bash
# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/utils.sh"

# Now you can use the functions
log_info "Starting script..."
start_timer "main_operation"

# ... do work ...

log_timer "main_operation"
log_success "Script completed!"
```

## Other Scripts

- `setup-project.sh` - Initial project setup and dependency installation
- `setup-python.sh` - Python environment configuration  
- `enforce-style.sh` - Code formatting and linting enforcement