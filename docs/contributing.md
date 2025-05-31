# Contributing to Dev-Env

Thank you for your interest in contributing to dev-env! This guide will help you get started with development, testing, and submitting changes.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Documentation](#documentation)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a Code of Conduct that all contributors are expected to follow:

1. **Be Respectful**: Treat all contributors with respect and professionalism
2. **Be Inclusive**: Welcome contributors of all backgrounds and experience levels
3. **Be Constructive**: Provide helpful feedback and accept criticism gracefully
4. **Be Patient**: Remember that everyone is learning and improving

## Getting Started

### Understanding the Project

Before contributing, familiarize yourself with:

1. **[Architecture Overview](architecture/overview.md)** - System design and principles
2. **[API Reference](developer/api-reference.md)** - Module documentation
3. **[Security Model](developer/security-model.md)** - Security implementation

### Types of Contributions

We welcome various types of contributions:

- **Bug Fixes**: Fix issues in the codebase
- **Features**: Add new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add test coverage
- **Performance**: Optimize existing code
- **Security**: Identify and fix security issues

## Development Setup

### Prerequisites

- Python 3.13 or higher
- Docker installed and running
- Git configured with your GitHub account
- Text editor or IDE with Python support

### Setting Up Your Development Environment

1. **Fork and Clone**
   ```bash
   # Fork the repository on GitHub
   # Clone your fork
   git clone git@github.com:yourusername/dev-env.git
   cd dev-env
   ```

2. **Create Development Environment**
   ```bash
   # Create a virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install in development mode
   pip install -e .
   
   # Install development dependencies
   pip install -r requirements-dev.txt
   ```

3. **Set Up Pre-commit Hooks**
   ```bash
   # Install pre-commit
   pip install pre-commit
   
   # Install git hooks
   pre-commit install
   ```

### Using Dev-Env for Development

You can use dev-env itself for development:

```python
# dev-env-dev.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="dev-env-dev",
    base_image="python:3.13",
    git=GitConfig(
        url="git@github.com:yourusername/dev-env.git",
        branch="feature/my-feature"
    ),
    volumes=[
        VolumeMount(source=".", target="/workspace"),
        VolumeMount(
            source="dev-env-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "PYTHONPATH": "/workspace/src"
    }
)
```

## Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications:

```python
# Good: Clear, descriptive names
def validate_container_configuration(config: dict) -> list[str]:
    """Validate container configuration and return errors"""
    errors = []
    
    if not config.get("image"):
        errors.append("Image is required")
    
    return errors

# Bad: Unclear names, no type hints
def validate(c):
    e = []
    if not c.get("image"):
        e.append("Image required")
    return e
```

### Key Principles

1. **Zero Dependencies**: Use only Python standard library
   ```python
   # Good: Using stdlib
   import json
   import sqlite3
   from pathlib import Path
   
   # Bad: External dependencies
   import requests  # NO!
   import yaml     # NO!
   ```

2. **Type Hints**: Always use type hints
   ```python
   def process_data(
       input_data: dict[str, Any],
       options: list[str] | None = None
   ) -> tuple[bool, str]:
       """Process data and return success status and message"""
       # Implementation
       return True, "Success"
   ```

3. **Error Handling**: Explicit and helpful
   ```python
   # Good: Specific error with context
   if not Path(config_file).exists():
       raise ConfigError(
           f"Configuration file not found: {config_file}",
           "Create a configuration file or specify a valid path"
       )
   
   # Bad: Generic error
   if not Path(config_file).exists():
       raise Exception("File not found")
   ```

4. **Documentation**: Clear and concise
   ```python
   def create_container(
       name: str,
       image: str,
       **kwargs
   ) -> str:
       """Create a Docker container.
       
       Args:
           name: Container name
           image: Docker image name
           **kwargs: Additional container options
           
       Returns:
           Container ID
           
       Raises:
           DockerError: If container creation fails
       """
   ```

### File Organization

```
src/dev_env/
├── __init__.py       # Package initialization
├── __main__.py       # Entry point
├── cli.py            # Command-line interface
├── config.py         # Configuration classes
├── docker.py         # Docker client
├── state.py          # State management
├── utils.py          # Utility functions
└── completion.py     # Shell completion
```

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest configuration
├── fixtures/                # Test fixtures
│   ├── __init__.py
│   └── docker_helpers.py
├── test_cli.py              # CLI tests
├── test_config.py           # Configuration tests
├── test_docker.py           # Docker client tests
├── test_state.py            # State management tests
├── test_utils.py            # Utility tests
└── test_integration.py      # Integration tests
```

### Writing Tests

1. **Unit Tests**
   ```python
   # tests/test_config.py
   import pytest
   from dev_env.config import Environment, VolumeMount
   
   def test_environment_creation():
       """Test basic environment creation"""
       env = Environment(
           name="test",
           base_image="python:3.13"
       )
       
       assert env.name == "test"
       assert env.base_image == "python:3.13"
       assert env.user == "1000:1000"  # Default
   
   def test_volume_mount_validation():
       """Test volume mount validation"""
       with pytest.raises(ValueError, match="Invalid volume mode"):
           VolumeMount(
               source="/src",
               target="/app",
               mode="invalid"
           )
   ```

2. **Integration Tests**
   ```python
   # tests/test_integration.py
   @pytest.mark.integration
   def test_container_lifecycle():
       """Test complete container lifecycle"""
       # Requires Docker to be running
       docker = DockerClient()
       
       # Create container
       container_id = docker.create_container(
           name="test-container",
           image="alpine:latest"
       )
       
       try:
           # Start container
           docker.start_container(container_id)
           
           # Verify running
           info = docker.inspect_container(container_id)
           assert info["State"]["Running"]
           
       finally:
           # Cleanup
           docker.stop_container(container_id)
           docker.remove_container(container_id)
   ```

3. **Fixtures**
   ```python
   # tests/conftest.py
   import pytest
   import tempfile
   from pathlib import Path
   
   @pytest.fixture
   def temp_state_dir():
       """Provide temporary state directory"""
       with tempfile.TemporaryDirectory() as tmpdir:
           yield Path(tmpdir)
   
   @pytest.fixture
   def mock_docker_socket(monkeypatch):
       """Mock Docker socket for testing"""
       def mock_connect(self):
           pass
       
       monkeypatch.setattr(
           "dev_env.docker.UnixHTTPConnection.connect",
           mock_connect
       )
   ```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=dev_env --cov-report=html

# Run specific test file
pytest tests/test_config.py

# Run only unit tests (skip integration)
pytest -m "not integration"

# Run with verbose output
pytest -v

# Run in parallel
pytest -n auto
```

### Test Requirements

- **Coverage**: Aim for >80% code coverage
- **Speed**: Unit tests should run in <1 second each
- **Isolation**: Tests must not depend on each other
- **Clarity**: Test names should describe what they test

## Submitting Changes

### Workflow

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Make Changes**
   - Write code following coding standards
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit Changes**
   ```bash
   # Stage changes
   git add -p
   
   # Commit with descriptive message
   git commit -m "feat: add volume mount validation
   
   - Add validation for volume mount paths
   - Prevent mounting system directories
   - Add tests for validation logic
   
   Fixes #123"
   ```

### Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Build/tooling changes

**Examples:**
```bash
feat(docker): add container health check support

fix(cli): handle missing config file gracefully

docs(api): update Environment class documentation

test(state): add concurrent access tests
```

### Pull Request Process

1. **Push Your Branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Use a descriptive title
   - Reference related issues
   - Describe what changed and why
   - Include test results

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Tests pass locally
   - [ ] New tests added
   - [ ] Coverage maintained/improved
   
   ## Checklist
   - [ ] Code follows style guide
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] No new dependencies added
   ```

4. **Code Review**
   - Address reviewer feedback
   - Update PR as needed
   - Ensure CI passes

## Documentation

### Documentation Standards

1. **User Documentation**
   - Clear, task-focused
   - Include examples
   - Avoid jargon

2. **API Documentation**
   - Complete docstrings
   - Type hints
   - Usage examples

3. **Architecture Documentation**
   - Explain design decisions
   - Include diagrams where helpful
   - Keep updated with code

### Building Documentation

```bash
# Generate API documentation
python -m pydoc -w dev_env

# Serve documentation locally
python -m http.server --directory docs 8000
```

## Release Process

### Version Numbering

We use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backwards compatible)
- **PATCH**: Bug fixes

### Release Checklist

1. **Update Version**
   ```python
   # src/dev_env/__init__.py
   __version__ = "0.2.0"
   ```

2. **Update Changelog**
   ```markdown
   # CHANGELOG.md
   ## [0.2.0] - 2024-01-15
   ### Added
   - Container health checks
   - Network isolation options
   
   ### Fixed
   - SSH key injection on Alpine Linux
   ```

3. **Run Full Test Suite**
   ```bash
   pytest
   pytest --integration
   ```

4. **Create Release**
   ```bash
   git tag -a v0.2.0 -m "Release version 0.2.0"
   git push origin v0.2.0
   ```

## Getting Help

### Resources

- **Issue Tracker**: Report bugs or request features
- **Discussions**: Ask questions and share ideas
- **Documentation**: Read the comprehensive docs
- **Examples**: Check the examples directory

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and discussions
- **Pull Requests**: Code contributions

### First-Time Contributors

If you're new to open source:

1. Look for issues labeled `good first issue`
2. Read the documentation thoroughly
3. Ask questions if you're unsure
4. Start small - even typo fixes are valuable!

## Recognition

Contributors are recognized in:
- The project README
- Release notes
- The AUTHORS file

Thank you for contributing to dev-env! Your efforts help make development environments better for everyone.