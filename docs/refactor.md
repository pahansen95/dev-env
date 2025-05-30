# Test Quality Improvement Plan for dev-env

## Overview

This plan provides a structured approach to improving test coverage from the current 45.53% to the target 85%. Follow these steps sequentially to ensure systematic improvement while maintaining code quality.

## Current State
- **Coverage**: 45.53% (530/1164 lines)
- **Target**: 85%
- **Gap**: 39.47% (~460 lines)
- **Critical Gap**: Docker module at 17.46% coverage

## Phase 1: Quick Wins (Days 1-3)
*Target: Reach 55% coverage*

### Task 1.1: Test Entry Points
**Files**: `__main__.py`, `completion.py` (partial)
**Estimated Coverage Gain**: +2%

```python
# tests/test_main.py
def test_main_entry_point():
    """Test the main module entry point"""
    with patch('dev_env.cli.main') as mock_main:
        from dev_env.__main__ import __name__
        # This executes the module
        mock_main.assert_called_once()
```

### Task 1.2: Add Simple Utility Tests
**File**: `utils.py`
**Estimated Coverage Gain**: +5%

Focus on these easy-to-test functions:
- `hash_file()` - Test with temporary files
- `hash_config()` - Test with sample dictionaries
- `format_size()` - Test size formatting
- `parse_port_mapping()` - Test various port formats

```python
# tests/unit/test_utils_simple.py
def test_hash_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    hash1 = hash_file(test_file)
    assert len(hash1) == 64  # SHA256 hex length
    
    # Same content = same hash
    hash2 = hash_file(test_file)
    assert hash1 == hash2

def test_parse_port_mapping():
    assert parse_port_mapping("80") == (80, 80)
    assert parse_port_mapping("8080:80") == (8080, 80)
    with pytest.raises(ValueError):
        parse_port_mapping("invalid:port:format")
```

### Task 1.3: Test Configuration Validation
**File**: `config.py`
**Estimated Coverage Gain**: +3%

Add tests for validation edge cases:

```python
# tests/unit/test_config_validation.py
def test_environment_memory_parsing():
    """Test memory string parsing"""
    env = Environment(name="test", base_image="alpine", memory="512m")
    assert env._parse_memory("512m") == 512 * 1024 * 1024
    
    # Test invalid formats
    with pytest.raises(ValueError):
        env._parse_memory("invalid")

def test_environment_cpu_validation():
    """Test CPU limit validation"""
    with pytest.raises(ValueError):
        Environment(name="test", base_image="alpine", cpus=-1)
```

## Phase 2: Docker Module Testing (Days 4-7)
*Target: Reach 70% coverage*

### Task 2.1: Mock Docker API Responses
**File**: `docker.py`
**Estimated Coverage Gain**: +10%

Create a test helper for mocking Docker responses:

```python
# tests/fixtures/docker_helpers.py
class DockerTestHelper:
    @staticmethod
    def mock_successful_response(data):
        """Create a successful API response mock"""
        response = Mock()
        response.status = 200
        response.read.return_value = json.dumps(data).encode()
        return response
    
    @staticmethod
    def mock_error_response(status, message):
        """Create an error API response mock"""
        response = Mock()
        response.status = status
        response.read.return_value = json.dumps({"message": message}).encode()
        return response
```

### Task 2.2: Test Container Operations
**Priority**: Container lifecycle methods
**Estimated Coverage Gain**: +8%

Test these methods in order:
1. `ping()` - Simple connectivity test
2. `list_containers()` - List operation
3. `get_container()` - Single container fetch
4. `start_container()` - State change operation
5. `stop_container()` - State change with timeout

```python
# tests/unit/test_docker_operations.py
@patch('dev_env.docker.UnixHTTPConnection')
def test_container_operations(mock_conn_class):
    helper = DockerTestHelper()
    mock_conn = Mock()
    mock_conn_class.return_value = mock_conn
    
    # Test list containers
    mock_conn.getresponse.return_value = helper.mock_successful_response([
        {"Id": "abc123", "Names": ["/test"], "State": "running"}
    ])
    
    client = DockerClient()
    containers = client.list_containers(all=True)
    assert len(containers) == 1
    assert containers[0]["Id"] == "abc123"
```

### Task 2.3: Test Error Scenarios
**Estimated Coverage Gain**: +5%

Test common Docker errors:

```python
# tests/unit/test_docker_errors.py
def test_docker_connection_refused():
    """Test handling when Docker daemon is unavailable"""
    with patch('socket.socket') as mock_socket:
        mock_socket.return_value.connect.side_effect = ConnectionRefusedError
        assert not check_docker_available()

def test_docker_api_errors():
    """Test various API error responses"""
    test_cases = [
        (404, "No such container"),
        (409, "Container already exists"),
        (500, "Internal server error"),
    ]
    
    for status, message in test_cases:
        # Test each error scenario
        pass
```

## Phase 3: CLI Error Paths (Days 8-10)
*Target: Reach 80% coverage*

### Task 3.1: Test Command Error Handling
**Files**: `cli.py`
**Estimated Coverage Gain**: +7%

Focus on untested error paths in each command:

```python
# tests/unit/test_cli_errors.py
class TestCLIErrorHandling:
    def test_up_command_errors(self):
        """Test various failure modes in up command"""
        # Test configuration load failure
        # Test docker unavailable
        # Test image pull failure
        # Test container creation failure
        
    def test_down_command_errors(self):
        """Test failure modes in down command"""
        # Test environment not found
        # Test container already removed
        # Test volume removal failure
```

### Task 3.2: Test User Input Handling
**Estimated Coverage Gain**: +3%

Test interactive prompts and user responses:

```python
@patch('builtins.input')
def test_user_confirmation(mock_input):
    """Test user confirmation on warnings"""
    # Test 'yes' response
    mock_input.return_value = 'y'
    # ... test continues
    
    # Test 'no' response
    mock_input.return_value = 'n'
    # ... test aborts
```

## Phase 4: Integration Testing (Days 11-14)
*Target: Reach 85% coverage*

### Task 4.1: Create Integration Test Suite
**Estimated Coverage Gain**: +5%

Add real Docker tests with proper markers:

```python
# tests/integration/test_real_docker.py
@pytest.mark.integration
@pytest.mark.skipif(not check_docker_available(), reason="Docker required")
class TestRealDocker:
    def test_minimal_container(self):
        """Test with real Docker daemon"""
        # Use alpine for fast tests
        # Always cleanup containers
```

### Task 4.2: End-to-End Workflow Tests
**Estimated Coverage Gain**: +3%

Test complete user workflows:

```python
# tests/integration/test_workflows.py
@pytest.mark.slow
def test_complete_dev_workflow(tmp_path):
    """Test from config creation to environment teardown"""
    # 1. Create config file
    # 2. Run 'up' command
    # 3. Execute command in container
    # 4. Run 'down' command
    # 5. Verify cleanup
```

## Best Practices for Test Implementation

### 1. Test Organization
```
tests/
├── unit/           # Fast, no external dependencies
├── integration/    # Requires Docker
├── fixtures/       # Shared test helpers
└── data/          # Test data files
```

### 2. Use Descriptive Test Names
```python
# Good
def test_docker_pull_image_handles_network_timeout():

# Bad
def test_pull_error():
```

### 3. Follow AAA Pattern
```python
def test_example():
    # Arrange - Set up test data
    config = create_test_config()
    
    # Act - Execute the code
    result = function_under_test(config)
    
    # Assert - Verify results
    assert result.status == "success"
```

### 4. Use Fixtures for Common Setup
```python
@pytest.fixture
def mock_docker_client():
    """Provides a mocked Docker client"""
    with patch('dev_env.docker.DockerClient') as mock:
        client = mock.return_value
        # Configure common responses
        yield client
```

### 5. Test Both Success and Failure Paths
```python
def test_operation():
    # Test success case
    assert operation(valid_input) == expected_result
    
    # Test failure case
    with pytest.raises(ExpectedError):
        operation(invalid_input)
```

## Running Tests

### Daily Development
```bash
# Run only unit tests (fast)
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src/dev_env --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_docker.py -v
```

### Before Committing
```bash
# Run all tests
pytest

# Check coverage threshold
pytest --cov=src/dev_env --cov-fail-under=85
```

### CI Pipeline
```bash
# Full test suite with reports
python helpers/run-tests.sh --type all --coverage yes --format junit
```

## Measuring Progress

Track your progress daily:

1. **Run coverage report**:
   ```bash
   pytest --cov=src/dev_env --cov-report=html
   open htmlcov/index.html
   ```

2. **Focus on red (uncovered) lines** in the HTML report

3. **Update this checklist**:
   - [ ] Phase 1: Quick Wins (Target: 55%)
   - [ ] Phase 2: Docker Module (Target: 70%)
   - [ ] Phase 3: CLI Errors (Target: 80%)
   - [ ] Phase 4: Integration (Target: 85%)

## Common Pitfalls to Avoid

1. **Don't test implementation details** - Test behavior, not internals
2. **Don't skip error cases** - They're often where bugs hide
3. **Don't write tests without assertions** - Every test must verify something
4. **Don't ignore flaky tests** - Fix them immediately
5. **Don't test external libraries** - Focus on your code

## Getting Help

- **Coverage Report**: Shows which lines need tests
- **Existing Tests**: Use as examples for new tests
- **Test Fixtures**: Reuse common setup code
- **CI Logs**: Check why tests fail in CI

## Success Criteria

You've succeeded when:
- Overall coverage reaches 85%
- All tests pass consistently
- Docker module coverage exceeds 60%
- No critical paths remain untested
- Tests run in under 30 seconds (excluding integration tests)