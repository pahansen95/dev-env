# Dev-Env Test Suite Fix Implementation Plan

## Phase 1: Critical Fixes (Execute Immediately)

### Fix 1: Update Container Name Generation Test

**File**: `tests/test_core.py`

**Current Code** (line ~185):
```python
def test_generate_container_name(self):
    result = generate_container_name("my-env")
    assert result == "dev-env-my-env"
```

**Replace With**:
```python
def test_generate_container_name(self):
    result = generate_container_name("my-env")
    assert result.startswith("devenv-my-env-")
    assert len(result) == len("devenv-my-env-") + 8  # 8 character hash suffix
    # Verify hash contains only hex characters
    hash_suffix = result.split("-")[-1]
    assert all(c in "0123456789abcdef" for c in hash_suffix)
```

### Fix 2: Add Network Column to Database Schema

**File**: `src/dev_env/state.py`

**Current Code** (line ~28):
```sql
CREATE TABLE IF NOT EXISTS environments (
    name TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    container_name TEXT NOT NULL,
    config TEXT NOT NULL,
    volumes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

**Replace With**:
```sql
CREATE TABLE IF NOT EXISTS environments (
    name TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    container_name TEXT NOT NULL,
    config TEXT NOT NULL,
    volumes TEXT,
    network TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```

**Additional Changes in Same File**:

1. Update `save_environment` method (line ~67):
```python
conn.execute(
    """
    INSERT OR REPLACE INTO environments
    (name, container_id, container_name, config, volumes, network, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?,
        COALESCE((SELECT created_at FROM environments WHERE name = ?), ?),
        ?)
    """,
    (
        name,
        state["container_id"],
        state["container_name"],
        json.dumps(state.get("config", {})),
        json.dumps(state.get("volumes", [])),
        state.get("network"),  # Add this line
        name,
        now,
        now,
    ),
)
```

2. Update `get_environment` method return (line ~97):
```python
return {
    "name": row["name"],
    "container_id": row["container_id"],
    "container_name": row["container_name"],
    "config": json.loads(row["config"]),
    "volumes": json.loads(row["volumes"]) if row["volumes"] else [],
    "network": row["network"],  # Add this line
    "created_at": row["created_at"],
    "updated_at": row["updated_at"],
}
```

3. Update `list_environments` method (line ~113):
```python
row["name"]: {
    "container_id": row["container_id"],
    "container_name": row["container_name"],
    "config": json.loads(row["config"]),
    "volumes": json.loads(row["volumes"]) if row["volumes"] else [],
    "network": row["network"],  # Add this line
    "created_at": row["created_at"],
    "updated_at": row["updated_at"],
}
```

### Fix 3: Add Missing Imports to Integration Tests

**File**: `tests/test_integration.py`

**Add at top of file** (after line 3):
```python
from unittest.mock import Mock, patch
import pytest
```

### Fix 4: Fix Environment Attribute Access

**File**: `tests/test_core.py`

**Search and Replace** throughout the file:
- `env.security.user` → `env.user`
- `env.security.drop_capabilities` → `env.drop_capabilities`
- `env.security.no_new_privileges` → `env.no_new_privileges`
- `env.resources.memory` → `env.memory`
- `env.resources.cpus` → `env.cpus`

### Fix 5: Correct Port Mapping Format

**File**: `tests/test_core.py`

**Current Code** (line ~75):
```python
ports={22: 2222, 8000: 8000},
```

**Replace With**:
```python
ports={22: {"HostPort": 2222}, 8000: {"HostPort": 8000}},
```

**Apply same fix to**:
- `tests/test_integration.py`
- `tests/conftest.py` (in `sample_environment` fixture)

## Phase 2: Test Infrastructure Updates

### Fix 6: Create Proper Mock for Docker Streaming

**File**: `tests/conftest.py`

**Add New Fixture**:
```python
@pytest.fixture
def mock_docker_streaming():
    """Mock Docker client with streaming pull support"""
    with patch("dev_env.docker.DockerClient") as mock_client:
        mock_instance = Mock(spec=DockerClient)
        mock_client.return_value = mock_instance
        
        # Setup streaming response mock
        def mock_pull_image(image, progress_callback=None):
            if progress_callback:
                progress_callback("Pulling from library/python", 0.0)
                progress_callback("Downloading", 50.0)
                progress_callback("Pull complete", 100.0)
        
        mock_instance.pull_image.side_effect = mock_pull_image
        mock_instance._parse_image_spec.return_value = ("docker.io", "library/python", "3.13")
        
        yield mock_instance
```

### Fix 7: Add State Migration for Existing Databases

**File**: `src/dev_env/state.py`

**Add method after `_init_db`** (line ~45):
```python
def _migrate_schema(self):
    """Migrate database schema to current version"""
    with self._get_conn() as conn:
        # Check if network column exists
        cursor = conn.execute("PRAGMA table_info(environments)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if "network" not in columns:
            # Add network column to existing table
            conn.execute("ALTER TABLE environments ADD COLUMN network TEXT")
```

**Update `__init__` method** (line ~22):
```python
def __init__(self, state_dir: Path):
    self.state_dir = state_dir
    self.state_dir.mkdir(parents=True, exist_ok=True)
    self.db_path = self.state_dir / "environments.db"
    self._init_db()
    self._migrate_schema()  # Add this line
```

## Phase 3: Add Missing Unit Tests

### Fix 8: Create SSH Utility Tests

**Create New File**: `tests/test_ssh_utils.py`

```python
"""Tests for SSH utility functions"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dev_env.utils import (
    setup_ssh_server,
    inject_ssh_key,
    get_host_ssh_key,
    ensure_ssh_config,
    remove_ssh_config,
)


class TestSSHUtilities:
    """Test SSH-related utility functions"""
    
    def test_setup_ssh_server_debian(self):
        """Test SSH server setup on Debian-based systems"""
        mock_docker = Mock()
        mock_docker.exec_run.side_effect = [
            (b"/usr/bin/apt-get", 0),  # which apt-get
            (b"", 0),  # apt-get update
            (b"", 0),  # apt-get install
            (b"", 0),  # mkdir
            (b"", 0),  # chmod
            (b"", 0),  # ssh-keygen -A
            (b"", 0),  # write sshd_config
        ]
        
        setup_ssh_server(mock_docker, "test123")
        
        # Verify package installation
        assert any("apt-get" in str(call) for call in mock_docker.exec_run.call_args_list)
        assert any("openssh-server" in str(call) for call in mock_docker.exec_run.call_args_list)
    
    def test_inject_ssh_key(self):
        """Test SSH key injection"""
        mock_docker = Mock()
        mock_docker.exec_run.return_value = (b"", 0)
        
        test_key = "ssh-rsa AAAAB3NzaC1yc2EA... test@example.com"
        inject_ssh_key(mock_docker, "test123", test_key)
        
        # Verify key was written and permissions set
        calls = mock_docker.exec_run.call_args_list
        assert len(calls) == 2
        assert "authorized_keys" in str(calls[0])
        assert "chmod" in str(calls[1])
    
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_get_host_ssh_key_existing(self, mock_read, mock_exists):
        """Test retrieving existing host SSH key"""
        mock_exists.return_value = True
        mock_read.return_value = "ssh-rsa AAAAB3... user@host\n"
        
        result = get_host_ssh_key()
        assert result == "ssh-rsa AAAAB3... user@host"
        assert mock_exists.called
    
    def test_ensure_ssh_config(self, tmp_path):
        """Test SSH config entry creation"""
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        config_file = ssh_dir / "config"
        
        with patch("pathlib.Path.home", return_value=tmp_path):
            ensure_ssh_config("test-container", 2222)
        
        assert config_file.exists()
        content = config_file.read_text()
        assert "Host devenv-test-container" in content
        assert "Port 2222" in content
```

### Fix 9: Create Git Utility Tests

**Create New File**: `tests/test_git_utils.py`

```python
"""Tests for Git utility functions"""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from dev_env.utils import (
    setup_git_in_container,
    get_host_git_config,
    clone_git_repository,
)
from dev_env.config import GitConfig


class TestGitUtilities:
    """Test Git-related utility functions"""
    
    def test_setup_git_in_container(self):
        """Test Git setup and repository cloning"""
        mock_docker = Mock()
        mock_docker.exec_run.side_effect = [
            (b"/usr/bin/git", 0),  # which git (already installed)
            (b"", 0),  # git config user.name
            (b"", 0),  # git config user.email
            (b"", 0),  # mkdir -p
            (b"", 0),  # git clone
        ]
        
        git_config = GitConfig(
            url="https://github.com/test/repo.git",
            branch="main",
            path="/workspace",
            shallow=True
        )
        
        host_config = {
            "user.name": "Test User",
            "user.email": "test@example.com"
        }
        
        setup_git_in_container(mock_docker, "test123", git_config, host_config)
        
        # Verify git configuration
        calls = [str(call) for call in mock_docker.exec_run.call_args_list]
        assert any("user.name" in call and "Test User" in call for call in calls)
        assert any("user.email" in call and "test@example.com" in call for call in calls)
        assert any("--depth" in call and "1" in call for call in calls)
    
    @patch("subprocess.run")
    def test_get_host_git_config(self, mock_run):
        """Test retrieving host Git configuration"""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="John Doe\n"),
            Mock(returncode=0, stdout="john@example.com\n"),
        ]
        
        config = get_host_git_config()
        assert config["user.name"] == "John Doe"
        assert config["user.email"] == "john@example.com"
```

### Fix 10: Create Security Validation Tests

**Create New File**: `tests/test_security.py`

```python
"""Tests for security validation functions"""

import pytest
from pathlib import Path

from dev_env.utils import (
    validate_volume_security,
    validate_port_security,
    apply_security_defaults,
    ConfigError,
)
from dev_env.config import Environment, VolumeMount


class TestSecurityValidation:
    """Test security validation functions"""
    
    def test_validate_volume_security_forbidden_paths(self):
        """Test detection of forbidden mount paths"""
        forbidden_volumes = [
            VolumeMount(source="/etc", target="/etc"),
            VolumeMount(source="/var/run/docker.sock", target="/docker.sock"),
            VolumeMount(source="/proc", target="/proc"),
        ]
        
        for vol in forbidden_volumes:
            with pytest.raises(ConfigError) as exc_info:
                validate_volume_security([vol])
            assert "security violation" in str(exc_info.value)
    
    def test_validate_volume_security_allowed_paths(self):
        """Test allowed mount paths pass validation"""
        allowed_volumes = [
            VolumeMount(source="/home/user/project", target="/workspace"),
            VolumeMount(source="named-volume", target="/data"),
            VolumeMount(source="./relative", target="/app"),
        ]
        
        # Should not raise any exceptions
        validate_volume_security(allowed_volumes)
    
    def test_validate_port_security_localhost_only(self):
        """Test port security enforces localhost binding"""
        ports = {
            22: {"HostPort": 2222},  # No HostIp specified
            80: {"HostPort": 8080, "HostIp": ""},  # Empty HostIp
        }
        
        validate_port_security(ports)
        
        # Verify localhost binding was applied
        assert ports[22]["HostIp"] == "127.0.0.1"
        assert ports[80]["HostIp"] == "127.0.0.1"
    
    def test_validate_port_security_reject_all_interfaces(self):
        """Test rejection of all-interface binding"""
        ports = {
            22: {"HostPort": 2222, "HostIp": "0.0.0.0"}
        }
        
        with pytest.raises(ConfigError) as exc_info:
            validate_port_security(ports)
        assert "0.0.0.0" in str(exc_info.value)
        assert "security violation" in str(exc_info.value)
    
    def test_apply_security_defaults(self):
        """Test security defaults are properly applied"""
        env = Environment(
            name="test",
            base_image="python:3.13",
            volumes=[
                VolumeMount(source="/tmp", target="/tmp"),
            ],
            ports={
                22: {"HostPort": 2222}
            }
        )
        
        apply_security_defaults(env)
        
        # Verify port was secured
        assert env.ports[22]["HostIp"] == "127.0.0.1"
```

## Phase 4: Integration Test Fixes

### Fix 11: Add Docker API Error Tests

**File**: `tests/test_docker.py` (create new)

```python
"""Tests for Docker client functionality"""

import pytest
import json
from unittest.mock import Mock, patch

from dev_env.docker import DockerClient, UnixHTTPConnection


class TestDockerClient:
    """Test Docker client implementation"""
    
    @patch("dev_env.docker.UnixHTTPConnection")
    def test_docker_api_error_handling(self, mock_conn_class):
        """Test proper error handling for Docker API errors"""
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 404
        mock_response.read.return_value = b'{"message": "No such image"}'
        mock_conn.getresponse.return_value = mock_response
        mock_conn_class.return_value = mock_conn
        
        client = DockerClient()
        
        with pytest.raises(RuntimeError) as exc_info:
            client._request("GET", "/images/nonexistent/json")
        
        assert "No such image" in str(exc_info.value)
    
    @patch("dev_env.docker.UnixHTTPConnection")
    def test_pull_image_streaming(self, mock_conn_class):
        """Test streaming image pull"""
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 200
        
        # Simulate streaming response
        progress_lines = [
            b'{"status": "Pulling from library/python", "id": "3.13"}\n',
            b'{"status": "Downloading", "progressDetail": {"current": 50, "total": 100}}\n',
            b'{"status": "Pull complete"}\n',
            b'',  # End of stream
        ]
        mock_response.readline.side_effect = progress_lines
        mock_conn.getresponse.return_value = mock_response
        mock_conn_class.return_value = mock_conn
        
        client = DockerClient()
        progress_updates = []
        
        def progress_callback(status, progress):
            progress_updates.append((status, progress))
        
        # First mock the image check (404 - not found)
        with patch.object(client, '_request') as mock_request:
            mock_request.side_effect = RuntimeError("Not found")
            client.pull_image("python:3.13", progress_callback)
        
        assert len(progress_updates) > 0
        assert any("Downloading" in update[0] for update in progress_updates)
```

## Phase 5: Execute Test Suite Validation

### Final Steps

1. **Run all tests with verbose output**:
   ```bash
   pytest -xvs tests/
   ```

2. **Check test coverage**:
   ```bash
   pytest --cov=src/dev_env --cov-report=term-missing tests/
   ```

3. **Run specific test categories**:
   ```bash
   # Unit tests only
   pytest -m unit tests/
   
   # Integration tests only
   pytest -m integration tests/
   ```

4. **Validate no import errors**:
   ```bash
   python -m py_compile src/dev_env/*.py
   ```

## Implementation Order

Execute fixes in this order to minimize test disruption:

1. **Day 1 Morning**: Fixes 1-5 (Critical fixes)
2. **Day 1 Afternoon**: Fixes 6-7 (Infrastructure)
3. **Day 2**: Fixes 8-10 (Unit tests)
4. **Day 3**: Fix 11 (Integration tests)
5. **Day 3**: Final validation

## Verification Checklist

- [ ] All test files import successfully
- [ ] Container name tests pass with pattern matching
- [ ] State manager handles network field properly
- [ ] No attribute access errors (flattened config)
- [ ] Port mappings use correct nested format
- [ ] Docker streaming tests work properly
- [ ] Security validation tests pass
- [ ] SSH utility tests complete
- [ ] Git utility tests complete
- [ ] Test coverage > 85%
- [ ] All tests pass on Python 3.13