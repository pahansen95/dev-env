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
  assert "up down list exec ssh logs" in script
  assert "complete -F _dev_env_completion dev-env" in script


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
  assert "__dev_env_list_environments" in script
  assert "complete -c dev-env" in script


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
  assert "__dev_env_list_environments" in captured.out


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
  expected_commands = ["up", "down", "list", "exec", "ssh", "logs"]

  bash_script = generate_bash_completion()
  zsh_script = generate_zsh_completion()
  fish_script = generate_fish_completion()

  for cmd in expected_commands:
    assert cmd in bash_script
    assert cmd in zsh_script
    assert cmd in fish_script
