"""Tests for state management operations"""

import pytest
import sqlite3

from dev_env.state import StateManager


class TestStateManager:
  """Test StateManager database operations"""

  def test_init_creates_database(self, temp_dir):
    """Test StateManager creates database file and tables"""
    state_dir = temp_dir / "state"
    manager = StateManager(state_dir)

    assert (state_dir / "environments.db").exists()

    # Check table exists
    with sqlite3.connect(state_dir / "environments.db") as conn:
      cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='environments'")
      assert cursor.fetchone() is not None

  def test_init_existing_database(self, state_manager):
    """Test StateManager works with existing database"""
    # Save an environment first
    state_manager.save_environment("test", {"container_id": "abc123"})

    # Create new manager with same path
    new_manager = StateManager(state_manager.state_dir)
    environments = new_manager.list_environments()

    assert "test" in environments
    assert environments["test"]["container_id"] == "abc123"

  def test_save_environment_new(self, state_manager):
    """Test saving new environment"""
    env_data = {
      "container_id": "container_123",
      "container_name": "test-container",
      "config": {"name": "test", "base_image": "python:3.13"},
      "volumes": ["test-vol"],
      "network": "test-network",
    }

    state_manager.save_environment("test-env", env_data)

    # Verify it was saved
    saved_env = state_manager.get_environment("test-env")
    assert saved_env is not None
    assert saved_env["container_id"] == "container_123"
    assert saved_env["config"]["name"] == "test"
    assert saved_env["volumes"] == ["test-vol"]

  def test_save_environment_update(self, state_manager):
    """Test updating existing environment"""
    # Save initial environment
    initial_data = {"container_id": "old_123", "status": "creating"}
    state_manager.save_environment("test", initial_data)

    # Update environment
    updated_data = {"container_id": "new_456", "status": "running"}
    state_manager.save_environment("test", updated_data)

    # Verify update
    saved_env = state_manager.get_environment("test")
    assert saved_env["container_id"] == "new_456"
    assert saved_env["status"] == "running"

  def test_get_environment_exists(self, state_manager):
    """Test getting existing environment"""
    env_data = {"container_id": "test_123", "image": "python:3.13"}
    state_manager.save_environment("my-env", env_data)

    result = state_manager.get_environment("my-env")
    assert result is not None
    assert result["container_id"] == "test_123"
    assert result["image"] == "python:3.13"

  def test_get_environment_not_exists(self, state_manager):
    """Test getting non-existent environment"""
    result = state_manager.get_environment("nonexistent")
    assert result is None

  def test_list_environments_empty(self, state_manager):
    """Test listing environments when none exist"""
    environments = state_manager.list_environments()
    assert environments == {}

  def test_list_environments_multiple(self, state_manager):
    """Test listing multiple environments"""
    # Save multiple environments
    state_manager.save_environment("env1", {"container_id": "c1", "status": "running"})
    state_manager.save_environment("env2", {"container_id": "c2", "status": "stopped"})
    state_manager.save_environment("env3", {"container_id": "c3", "status": "running"})

    environments = state_manager.list_environments()
    assert len(environments) == 3
    assert "env1" in environments
    assert "env2" in environments
    assert "env3" in environments
    assert environments["env1"]["container_id"] == "c1"
    assert environments["env2"]["status"] == "stopped"

  def test_remove_environment_exists(self, state_manager):
    """Test removing existing environment"""
    # Save environment first
    state_manager.save_environment("to-remove", {"container_id": "remove_123"})
    assert state_manager.get_environment("to-remove") is not None

    # Remove environment
    state_manager.remove_environment("to-remove")

    # Verify removal
    assert state_manager.get_environment("to-remove") is None
    assert "to-remove" not in state_manager.list_environments()

  def test_remove_environment_not_exists(self, state_manager):
    """Test removing non-existent environment (should not raise error)"""
    # Should not raise exception
    state_manager.remove_environment("nonexistent")

    # Database should still be functional
    environments = state_manager.list_environments()
    assert environments == {}

  def test_save_complex_environment_data(self, state_manager):
    """Test saving environment with complex nested data"""
    complex_data = {
      "container_id": "complex_123",
      "container_name": "complex-container",
      "config": {
        "name": "complex-env",
        "base_image": "python:3.13",
        "ports": {22: 2222, 8000: 8000},
        "environment": {"VAR1": "value1", "VAR2": "value2"},
        "volumes": [
          {"name": "data", "source": "data-vol", "target": "/data", "type": "named"},
          {"name": "bind", "source": "/tmp", "target": "/tmp", "type": "bind"},
        ],
        "network": {"name": "custom-net", "driver": "bridge"},
        "git": {"url": "https://github.com/test/repo.git", "branch": "main", "path": "/workspace"},
      },
      "volumes": ["data-vol"],
      "network": "custom-net",
      "created_at": "2024-01-01T00:00:00Z",
    }

    state_manager.save_environment("complex-env", complex_data)

    # Verify complex data was saved and loaded correctly
    saved_env = state_manager.get_environment("complex-env")
    assert saved_env is not None
    assert saved_env["container_id"] == "complex_123"
    assert saved_env["config"]["ports"] == {22: 2222, 8000: 8000}
    assert len(saved_env["config"]["volumes"]) == 2
    assert saved_env["config"]["git"]["url"] == "https://github.com/test/repo.git"
    assert saved_env["network"] == "custom-net"

  def test_json_serialization_edge_cases(self, state_manager):
    """Test JSON serialization handles edge cases"""
    edge_cases_data = {
      "container_id": "edge_123",
      "unicode_text": "Hello 世界 🌍",
      "special_chars": "\"quotes\" and 'apostrophes' and \\backslashes\\",
      "numbers": {"integer": 42, "float": 3.14159, "zero": 0, "negative": -123},
      "booleans": {"true": True, "false": False},
      "null_value": None,
      "empty_collections": {"list": [], "dict": {}, "string": ""},
    }

    state_manager.save_environment("edge-cases", edge_cases_data)

    # Verify edge cases were handled correctly
    saved_env = state_manager.get_environment("edge-cases")
    assert saved_env["unicode_text"] == "Hello 世界 🌍"
    assert saved_env["special_chars"] == "\"quotes\" and 'apostrophes' and \\backslashes\\"
    assert saved_env["numbers"]["float"] == 3.14159
    assert saved_env["booleans"]["true"] is True
    assert saved_env["null_value"] is None
    assert saved_env["empty_collections"]["list"] == []

  def test_database_connection_error_handling(self, temp_dir):
    """Test handling of database connection errors"""
    state_dir = temp_dir / "readonly"
    state_dir.mkdir(mode=0o444)  # Read-only directory

    try:
      # This should handle permission errors gracefully
      manager = StateManager(state_dir)
      # The init should succeed even if we can't write to the directory initially
      assert manager.state_dir == state_dir
    except PermissionError:
      # This is acceptable - some systems may prevent read-only directory creation
      pytest.skip("Cannot create read-only directory on this system")
    finally:
      # Clean up - make directory writable again
      state_dir.chmod(0o755)

  def test_concurrent_access_simulation(self, state_manager):
    """Test simulated concurrent access to state database"""
    # Simulate multiple rapid operations
    for i in range(10):
      env_name = f"concurrent-{i}"
      env_data = {"container_id": f"container_{i}", "iteration": i}
      state_manager.save_environment(env_name, env_data)

    # Verify all environments were saved
    environments = state_manager.list_environments()
    assert len(environments) == 10

    # Remove some environments
    for i in range(0, 10, 2):  # Remove even-numbered environments
      state_manager.remove_environment(f"concurrent-{i}")

    # Verify correct environments remain
    remaining = state_manager.list_environments()
    assert len(remaining) == 5
    for i in range(1, 10, 2):  # Odd-numbered should remain
      assert f"concurrent-{i}" in remaining

  def test_state_directory_creation(self, temp_dir):
    """Test state directory is created if it doesn't exist"""
    nested_path = temp_dir / "nested" / "state" / "directory"

    # Directory doesn't exist yet
    assert not nested_path.exists()

    # Create StateManager - should create directory
    manager = StateManager(nested_path)

    # Directory should now exist
    assert nested_path.exists()
    assert nested_path.is_dir()

    # Database file should be created
    assert (nested_path / "environments.db").exists()

  def test_environment_name_validation(self, state_manager):
    """Test environment names are handled correctly"""
    # Test various valid environment names
    valid_names = [
      "simple",
      "with-dashes",
      "with_underscores",
      "with123numbers",
      "CamelCase",
      "long-environment-name-with-many-parts",
    ]

    for name in valid_names:
      env_data = {"container_id": f"container_{name}", "name": name}
      state_manager.save_environment(name, env_data)

      saved_env = state_manager.get_environment(name)
      assert saved_env is not None
      assert saved_env["name"] == name

  def test_large_environment_data(self, state_manager):
    """Test handling of large environment data"""
    # Create large data structure
    large_data = {
      "container_id": "large_123",
      "large_list": list(range(1000)),  # 1000 integers
      "large_dict": {f"key_{i}": f"value_{i}" for i in range(500)},  # 500 key-value pairs
      "large_string": "x" * 10000,  # 10KB string
      "nested_structure": {
        "level1": {"level2": {"level3": {"data": [{"item": i, "value": f"value_{i}"} for i in range(100)]}}}
      },
    }

    state_manager.save_environment("large-env", large_data)

    # Verify large data was saved and loaded correctly
    saved_env = state_manager.get_environment("large-env")
    assert saved_env is not None
    assert len(saved_env["large_list"]) == 1000
    assert len(saved_env["large_dict"]) == 500
    assert len(saved_env["large_string"]) == 10000
    assert saved_env["nested_structure"]["level1"]["level2"]["level3"]["data"][50]["value"] == "value_50"
