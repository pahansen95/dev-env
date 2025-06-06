"""Tests for plumbing commands."""

import json
import pytest
from unittest.mock import Mock, patch
from argparse import Namespace

from dev_env.cli_plumbing import PlumbingCommand
from dev_env.commands.plumbing.context_create import ContextCreateCommand
from dev_env.commands.plumbing.context_resolve import ContextResolveCommand
from dev_env.commands.plumbing.context_list import ContextListCommand
from dev_env.context import Context


class TestPlumbingCommand:
  """Test base PlumbingCommand class."""

  def test_output_json(self, capsys):
    """Test JSON output."""

    class TestCommand(PlumbingCommand):
      def execute(self, args):
        return {"test": "value", "number": 42}

    cmd = TestCommand()
    cmd.run(Namespace())

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"test": "value", "number": 42}

  def test_error_handling(self, capsys):
    """Test error output."""

    class TestCommand(PlumbingCommand):
      def execute(self, args):
        raise ValueError("Test error")

    cmd = TestCommand()

    with pytest.raises(SystemExit) as exc_info:
      cmd.run(Namespace())

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["error"] == "Test error"
    assert output["code"] == "ValueError"


class TestContextCreateCommand:
  """Test context-create command."""

  def test_create_context(self, tmp_path, capsys):
    """Test creating a new context."""
    test_dir = tmp_path / "project"
    test_dir.mkdir()

    # Use isolated state directory
    with patch("dev_env.state.Path.home", return_value=tmp_path):
      args = Namespace(name="test", path=str(test_dir))
      cmd = ContextCreateCommand()
      cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["name"] == "test"
    assert output["path"] == str(test_dir)
    assert "id" in output
    assert "created_at" in output
    assert output["state"] == "active"

    # Verify .dev-env directory was created
    assert (test_dir / ".dev-env").exists()

  def test_create_context_path_not_found(self, capsys):
    """Test creating context with non-existent path."""
    args = Namespace(name="test", path="/nonexistent/path")
    cmd = ContextCreateCommand()
    cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["code"] == "PATH_NOT_FOUND"
    assert "Path does not exist" in output["error"]

  def test_create_duplicate_context(self, tmp_path, capsys):
    """Test creating duplicate context name."""
    test_dir = tmp_path / "project"
    test_dir.mkdir()

    # Use isolated state directory
    with patch("dev_env.state.Path.home", return_value=tmp_path):
      args = Namespace(name="test", path=str(test_dir))
      cmd = ContextCreateCommand()

      # Create first context
      cmd.run(args)
      capsys.readouterr()  # Clear output

      # Try to create duplicate
      cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["code"] == "CONTEXT_EXISTS"
    assert "already exists" in output["error"]


class TestContextResolveCommand:
  """Test context-resolve command."""

  def test_resolve_by_name(self, tmp_path, capsys):
    """Test resolving context by name."""
    # Create a context first
    test_dir = tmp_path / "project"
    test_dir.mkdir()

    with patch("dev_env.state.ContextManager") as MockManager:
      manager = Mock()
      MockManager.return_value = manager

      # Mock the create_context call
      context = Context(
        id="test-id",
        name="test",
        path=test_dir,
        created_at="2024-01-01T00:00:00",
        last_used="2024-01-01T00:00:00",
        state="active",
      )
      manager.create_context.return_value = context

      create_args = Namespace(name="test", path=str(test_dir))
      ContextCreateCommand().run(create_args)
      capsys.readouterr()  # Clear output

      # Mock the resolve call
      from dev_env.context_resolver import ContextResolver

      with patch.object(ContextResolver, "resolve", return_value=context):
        # Resolve by name
        args = Namespace(name="test")
        cmd = ContextResolveCommand()
        cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["name"] == "test"
    assert output["path"] == str(test_dir)
    assert "id" in output

  def test_resolve_not_found(self, capsys):
    """Test resolving non-existent context."""
    args = Namespace(name="nonexistent")
    cmd = ContextResolveCommand()
    cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["code"] == "CONTEXT_NOT_FOUND"

  @patch("pathlib.Path.cwd")
  def test_resolve_by_path(self, mock_cwd, tmp_path, capsys):
    """Test resolving context by current directory."""
    test_dir = tmp_path / "project"
    test_dir.mkdir()
    (test_dir / ".dev-env").mkdir()

    # Mock current directory
    mock_cwd.return_value = test_dir

    with patch("dev_env.state.ContextManager") as MockManager:
      manager = Mock()
      MockManager.return_value = manager

      # Mock the context resolution
      context = Context(
        id="test-id",
        name="test",
        path=test_dir,
        created_at="2024-01-01T00:00:00",
        last_used="2024-01-01T00:00:00",
        state="active",
      )

      from dev_env.context_resolver import ContextResolver

      with patch.object(ContextResolver, "resolve", return_value=context):
        # Resolve without name (should use cwd)
        args = Namespace(name=None)
        cmd = ContextResolveCommand()
        cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["name"] == "test"


class TestContextListCommand:
  """Test context-list command."""

  def test_list_empty(self, tmp_path, capsys):
    """Test listing when no contexts exist."""
    # Ensure complete isolation by mocking at the command level
    with patch("dev_env.commands.plumbing.context_list.ContextManager") as MockManager:
      manager = Mock()
      MockManager.return_value = manager
      manager.list_contexts.return_value = []

      args = Namespace()
      cmd = ContextListCommand()
      cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["contexts"] == []

  def test_list_multiple_contexts(self, tmp_path, capsys):
    """Test listing multiple contexts."""
    # Ensure complete isolation by mocking at the command level
    with patch("dev_env.commands.plumbing.context_list.ContextManager") as MockManager:
      manager = Mock()
      MockManager.return_value = manager

      # Mock the list_contexts call
      contexts = [
        Context(
          id=f"id-{i}",
          name=f"test{i}",
          path=tmp_path / f"project{i}",
          created_at="2024-01-01T00:00:00",
          last_used="2024-01-01T00:00:00",
          state="active",
        )
        for i in range(3)
      ]
      manager.list_contexts.return_value = contexts

      # List contexts
      args = Namespace()
      cmd = ContextListCommand()
      cmd.run(args)

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert len(output["contexts"]) == 3
    names = [c["name"] for c in output["contexts"]]
    assert "test0" in names
    assert "test1" in names
    assert "test2" in names
