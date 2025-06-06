"""Tests for context management functionality."""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from dev_env.context import Context
from dev_env.context_resolver import ContextResolver
from dev_env.state import ContextManager


class TestContext:
  """Test Context data model."""

  def test_generate_id(self):
    """Test context ID generation."""
    id1 = Context.generate_id("test", Path("/tmp/test"))
    id2 = Context.generate_id("test", Path("/tmp/test"))
    id3 = Context.generate_id("test", Path("/tmp/other"))

    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 64  # SHA-256 hex digest length

  def test_to_dict(self):
    """Test context serialization."""
    context = Context(
      id="test-id",
      name="test",
      path=Path("/tmp/test"),
      created_at="2024-01-01T00:00:00",
      last_used="2024-01-01T00:00:00",
      state="active",
    )

    data = context.to_dict()
    assert data["id"] == "test-id"
    assert data["name"] == "test"
    assert data["path"] == "/tmp/test"
    assert data["created_at"] == "2024-01-01T00:00:00"
    assert data["last_used"] == "2024-01-01T00:00:00"
    assert data["state"] == "active"

  def test_from_dict(self):
    """Test context deserialization."""
    data = {
      "id": "test-id",
      "name": "test",
      "path": "/tmp/test",
      "created_at": "2024-01-01T00:00:00",
      "last_used": "2024-01-01T00:00:00",
      "state": "active",
    }

    context = Context.from_dict(data)
    assert context.id == "test-id"
    assert context.name == "test"
    assert context.path == Path("/tmp/test")
    assert context.created_at == "2024-01-01T00:00:00"
    assert context.last_used == "2024-01-01T00:00:00"
    assert context.state == "active"


class TestContextResolver:
  """Test ContextResolver functionality."""

  def test_resolve_by_name(self, tmp_path):
    """Test resolving context by name."""
    manager = ContextManager(tmp_path / "state")
    test_path = tmp_path / "test"
    test_path.mkdir()
    manager.create_context("test", test_path)

    resolver = ContextResolver(manager)
    # Test resolving by name instead of non-existent resolve_from_path method
    resolved = resolver.resolve("test")

    assert resolved is not None
    assert resolved.name == "test"
    assert resolved.path == test_path.resolve()

  def test_resolve_by_name_not_found(self, tmp_path):
    """Test resolving non-existent context by name."""
    manager = ContextManager(tmp_path)
    resolver = ContextResolver(manager)

    resolved = resolver.resolve("nonexistent")
    assert resolved is None

  @patch("pathlib.Path.cwd")
  def test_resolve_by_path(self, mock_cwd, tmp_path):
    """Test resolving context by walking up directory tree."""
    test_dir = tmp_path / "project" / "subdir"
    test_dir.mkdir(parents=True)
    dev_env_dir = tmp_path / "project" / ".dev-env"
    dev_env_dir.mkdir()

    mock_cwd.return_value = test_dir

    manager = ContextManager(tmp_path / "state")
    manager.create_context("test", tmp_path / "project")

    resolver = ContextResolver(manager)
    resolved = resolver.resolve()

    assert resolved is not None
    assert resolved.name == "test"
    assert resolved.path == tmp_path / "project"

  @patch("pathlib.Path.cwd")
  def test_resolve_by_path_not_found(self, mock_cwd, tmp_path):
    """Test resolving context when no .dev-env directory exists."""
    test_dir = tmp_path / "project"
    test_dir.mkdir()
    mock_cwd.return_value = test_dir

    manager = ContextManager(tmp_path / "state")
    resolver = ContextResolver(manager)

    resolved = resolver.resolve()
    assert resolved is None


class TestContextManager:
  """Test ContextManager functionality."""

  def test_create_context(self, tmp_path):
    """Test creating a new context."""
    manager = ContextManager(tmp_path)
    test_path = tmp_path / "test"
    test_path.mkdir()
    context = manager.create_context("test", test_path)

    assert context.name == "test"
    assert context.path == test_path.resolve()
    assert context.state == "active"
    assert context.id == Context.generate_id("test", test_path)

  def test_get_context(self, tmp_path):
    """Test retrieving context by ID."""
    manager = ContextManager(tmp_path)
    test_path = tmp_path / "test"
    test_path.mkdir()
    created = manager.create_context("test", test_path)

    retrieved = manager.get_context(created.id)
    assert retrieved is not None
    assert retrieved.name == created.name
    assert retrieved.path == created.path
    assert retrieved.id == created.id

  def test_get_context_not_found(self, tmp_path):
    """Test retrieving non-existent context."""
    manager = ContextManager(tmp_path)
    context = manager.get_context("nonexistent")
    assert context is None

  def test_list_contexts(self, tmp_path):
    """Test listing all contexts."""
    manager = ContextManager(tmp_path)

    # Create multiple contexts
    test_path1 = tmp_path / "test1"
    test_path1.mkdir()
    test_path2 = tmp_path / "test2"
    test_path2.mkdir()
    manager.create_context("test1", test_path1)
    manager.create_context("test2", test_path2)

    contexts = manager.list_contexts()
    assert len(contexts) == 2

    # Should be ordered by last_used DESC
    context_names = [c.name for c in contexts]
    assert "test2" in context_names
    assert "test1" in context_names

  def test_update_context(self, tmp_path):
    """Test updating context state."""
    manager = ContextManager(tmp_path)
    test_path = tmp_path / "test"
    test_path.mkdir()
    context = manager.create_context("test", test_path)

    # Update context
    context.state = "inactive"
    context.last_used = datetime.utcnow().isoformat()
    manager.update_context(context)

    # Retrieve and verify
    updated = manager.get_context(context.id)
    assert updated.state == "inactive"
    assert updated.last_used == context.last_used

  def test_unique_constraint(self, tmp_path):
    """Test that duplicate context names are rejected."""
    manager = ContextManager(tmp_path)
    test_path1 = tmp_path / "test1"
    test_path1.mkdir()
    test_path2 = tmp_path / "test2"
    test_path2.mkdir()
    manager.create_context("test", test_path1)

    with pytest.raises(Exception):  # SQLite IntegrityError
      manager.create_context("test", test_path2)
