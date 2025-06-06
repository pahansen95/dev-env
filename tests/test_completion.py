"""Tests for shell completion generation"""

import argparse
from unittest.mock import Mock

from dev_env.completion import (
  generate_bash_completion,
  generate_zsh_completion,
  generate_fish_completion,
  cmd_completion,
  add_completion_parser,
)


def test_generate_bash_completion():
  """Test bash completion script generation"""
  script = generate_bash_completion()

  assert isinstance(script, str)
  assert len(script) > 0
  assert "_dev_env_completion" in script
  # Check for new commands
  assert "work stop run status shell" in script
  assert "context-create context-resolve context-list" in script
  assert "complete -F _dev_env_completion dev-env" in script
  # Ensure legacy commands are NOT present
  for legacy_cmd in ["up", "down", "list", "exec", "ssh", "logs"]:
    assert f" {legacy_cmd} " not in script


def test_generate_zsh_completion():
  """Test zsh completion script generation"""
  script = generate_zsh_completion()

  assert isinstance(script, str)
  assert len(script) > 0
  assert "#compdef dev-env" in script
  assert "_dev_env" in script
  assert "_arguments" in script


def test_generate_fish_completion():
  """Test fish completion script generation"""
  script = generate_fish_completion()

  assert isinstance(script, str)
  assert len(script) > 0
  assert "__dev_env_list_contexts" in script
  assert "complete -c dev-env" in script
  # Ensure legacy function name is NOT present
  assert "__dev_env_list_environments" not in script


def test_cmd_completion_bash(tmp_path, capsys):
  """Test completion command for bash shell"""
  args = Mock()
  args.shell = "bash"
  args.output = None

  result = cmd_completion(args)

  assert result == 0
  captured = capsys.readouterr()
  assert "_dev_env_completion" in captured.out


def test_cmd_completion_zsh(tmp_path, capsys):
  """Test completion command for zsh shell"""
  args = Mock()
  args.shell = "zsh"
  args.output = None

  result = cmd_completion(args)

  assert result == 0
  captured = capsys.readouterr()
  assert "#compdef dev-env" in captured.out


def test_cmd_completion_fish(tmp_path, capsys):
  """Test completion command for fish shell"""
  args = Mock()
  args.shell = "fish"
  args.output = None

  result = cmd_completion(args)

  assert result == 0
  captured = capsys.readouterr()
  assert "__dev_env_list_contexts" in captured.out
  # Ensure legacy function name is NOT present
  assert "__dev_env_list_environments" not in captured.out


def test_cmd_completion_unsupported_shell(capsys):
  """Test completion command with unsupported shell"""
  args = Mock()
  args.shell = "powershell"
  args.output = None

  result = cmd_completion(args)

  assert result == 1
  captured = capsys.readouterr()
  assert "Unsupported shell: powershell" in captured.out


def test_cmd_completion_with_output_file(tmp_path):
  """Test completion command writing to output file"""
  output_file = tmp_path / "completion.bash"

  args = Mock()
  args.shell = "bash"
  args.output = str(output_file)

  result = cmd_completion(args)

  assert result == 0
  assert output_file.exists()

  content = output_file.read_text()
  assert "_dev_env_completion" in content


def test_add_completion_parser():
  """Test adding completion parser to subparsers"""
  parser = argparse.ArgumentParser()
  subparsers = parser.add_subparsers()

  add_completion_parser(subparsers)

  # Parse completion command
  args = parser.parse_args(["completion", "bash"])
  assert args.shell == "bash"
  assert hasattr(args, "func")


def test_completion_script_content_completeness():
  """Test that completion scripts contain expected commands"""
  # New command structure
  porcelain_commands = ["work", "stop", "run", "status", "shell"]
  plumbing_commands = [
    "context-create",
    "context-resolve",
    "context-list",
    "env-create",
    "env-start",
    "env-stop",
    "env-status",
    "plumbing-exec",
    "plumbing-attach",
  ]

  bash_script = generate_bash_completion()
  zsh_script = generate_zsh_completion()
  fish_script = generate_fish_completion()

  # Check new commands are present
  for cmd in porcelain_commands + plumbing_commands:
    assert cmd in bash_script
    assert cmd in zsh_script
    assert cmd in fish_script

  # Ensure legacy commands are NOT present as standalone commands
  # Note: "list" might appear in "context-list", so we check for exact patterns
  legacy_patterns_bash = ['"up"', '"down"', '"exec"', '"ssh"', '"logs"']
  legacy_patterns_zsh = ["'up'", "'down'", "'exec'", "'ssh'", "'logs'"]
  legacy_patterns_fish = ['"up"', '"down"', '"exec"', '"ssh"', '"logs"']

  # For bash, check command definitions
  for pattern in legacy_patterns_bash:
    assert pattern not in bash_script

  # For zsh, check command definitions
  for pattern in legacy_patterns_zsh:
    assert pattern not in zsh_script

  # For fish, check command definitions
  for pattern in legacy_patterns_fish:
    assert pattern not in fish_script

  # Special check for "list" - ensure it only appears as part of "context-list"
  # In bash/zsh/fish completion scripts, standalone commands are typically quoted
  assert '"list"' not in bash_script
  assert "'list'" not in zsh_script
  assert '"list"' not in fish_script
