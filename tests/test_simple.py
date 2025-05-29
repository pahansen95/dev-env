"""Simple tests to verify test infrastructure works"""

from dev_env.config import Environment


class TestSimple:
  """Simple tests to verify basic functionality"""

  def test_environment_creation(self):
    """Test basic environment creation"""
    env = Environment(name="test-env", base_image="python:3.13")
    assert env.name == "test-env"
    assert env.base_image == "python:3.13"

  def test_environment_with_command(self):
    """Test environment with command"""
    env = Environment(name="cmd-env", base_image="ubuntu:22.04", command=["sleep", "infinity"])
    assert env.command == ["sleep", "infinity"]

  def test_environment_to_dict(self):
    """Test environment dictionary conversion"""
    env = Environment(name="dict-env", base_image="node:18")
    env_dict = env.to_dict()
    assert env_dict["name"] == "dict-env"
    assert env_dict["base_image"] == "node:18"
