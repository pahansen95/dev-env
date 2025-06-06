"""Test fixtures for isolated development environment testing."""

import pytest
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import Mock, MagicMock

from dev_env.state import StateManager
from dev_env.state import ContextManager
from dev_env.io import InputProvider


@pytest.fixture
def isolated_workspace() -> Generator[Dict[str, Path], None, None]:
  """Create isolated filesystem workspace for testing."""
  with tempfile.TemporaryDirectory() as temp_dir:
    temp_path = Path(temp_dir)

    workspace = temp_path / "workspace"
    workspace.mkdir()

    config_dir = workspace / ".dev-env"
    config_dir.mkdir()

    state_db = temp_path / "state.db"

    yield {"temp_dir": temp_path, "workspace": workspace, "config_dir": config_dir, "state_db": state_db}


@pytest.fixture
def isolated_state_manager(isolated_workspace) -> StateManager:
  """Create isolated StateManager for testing."""
  state_db_path = isolated_workspace["state_db"]
  return StateManager(state_db_path.parent)


@pytest.fixture
def isolated_context_manager(isolated_state_manager) -> ContextManager:
  """Create isolated ContextManager for testing."""
  return ContextManager(isolated_state_manager.state_dir)


@pytest.fixture
def mock_input_provider() -> InputProvider:
  """Create mock InputProvider for non-interactive testing."""
  mock = Mock(spec=InputProvider)
  mock.get_input.return_value = "test-context"
  mock.get_yes_no.return_value = True
  return mock


@pytest.fixture
def mock_docker_client():
  """Create mock DockerClient for testing."""
  mock = MagicMock()

  # Default successful responses
  mock.ping.return_value = True
  mock.create_container.return_value = {"Id": "test-container-id"}
  mock.start_container.return_value = None
  mock.stop_container.return_value = None
  mock.get_container.return_value = {"Id": "test-container-id", "State": {"Status": "running"}}

  return mock


@pytest.fixture
def standard_context(isolated_workspace) -> Dict[str, Any]:
  """Create standard test context data."""
  return {
    "id": "test-context-id-12345",
    "name": "test-context",
    "path": str(isolated_workspace["workspace"]),
    "created_at": "2025-01-01T00:00:00Z",
    "last_used": "2025-01-01T00:00:00Z",
    "state": "active",
  }


@pytest.fixture
def standard_env_status() -> Dict[str, Any]:
  """Create standard environment status response."""
  return {"state": "running", "context_name": "test-context", "container_id": "test-container-id"}


@pytest.fixture
def error_env_status() -> Dict[str, Any]:
  """Create error environment status response."""
  return {"error": "Environment not found", "state": "notfound"}


class TestArgs:
  """Simple args container for testing command interfaces."""

  def __init__(self, **kwargs):
    for key, value in kwargs.items():
      setattr(self, key, value)


@pytest.fixture
def test_args():
  """Factory for creating test argument objects."""
  return TestArgs


@pytest.fixture
def clean_database(isolated_workspace):
  """Ensure clean database state for each test."""
  db_path = isolated_workspace["state_db"]

  # Remove any existing database
  if db_path.exists():
    db_path.unlink()

  yield db_path

  # Cleanup after test
  if db_path.exists():
    db_path.unlink()
