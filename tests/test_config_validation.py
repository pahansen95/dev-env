"""Tests for configuration validation in config.py"""

import pytest
from dev_env.config import Environment, SecurityLevel


class TestEnvironmentMemoryParsing:
  """Test memory string parsing and validation"""

  def test_parse_memory_bytes(self):
    """Test parsing bytes values"""
    env = Environment(name="test", base_image="alpine")

    assert env._parse_memory("1024") == 1024
    assert env._parse_memory("1024b") == 1024
    assert env._parse_memory("1024B") == 1024
    assert env._parse_memory("  1024  ") == 1024

  def test_parse_memory_kilobytes(self):
    """Test parsing kilobyte values"""
    env = Environment(name="test", base_image="alpine")

    assert env._parse_memory("1k") == 1024
    assert env._parse_memory("1kb") == 1024
    assert env._parse_memory("1KB") == 1024
    assert env._parse_memory("2k") == 2048
    assert env._parse_memory("1.5k") == int(1.5 * 1024)

  def test_parse_memory_megabytes(self):
    """Test parsing megabyte values"""
    env = Environment(name="test", base_image="alpine")

    assert env._parse_memory("1m") == 1024 * 1024
    assert env._parse_memory("1mb") == 1024 * 1024
    assert env._parse_memory("1MB") == 1024 * 1024
    assert env._parse_memory("512m") == 512 * 1024 * 1024
    assert env._parse_memory("1.5m") == int(1.5 * 1024 * 1024)

  def test_parse_memory_gigabytes(self):
    """Test parsing gigabyte values"""
    env = Environment(name="test", base_image="alpine")

    assert env._parse_memory("1g") == 1024**3
    assert env._parse_memory("1gb") == 1024**3
    assert env._parse_memory("1GB") == 1024**3
    assert env._parse_memory("2g") == 2 * (1024**3)
    assert env._parse_memory("0.5g") == int(0.5 * 1024**3)

  def test_parse_memory_terabytes(self):
    """Test parsing terabyte values"""
    env = Environment(name="test", base_image="alpine")

    assert env._parse_memory("1t") == 1024**4
    assert env._parse_memory("1tb") == 1024**4
    assert env._parse_memory("1TB") == 1024**4

  def test_parse_memory_invalid_format(self):
    """Test that invalid memory formats raise ValueError"""
    env = Environment(name="test", base_image="alpine")

    with pytest.raises(ValueError, match="Invalid memory format"):
      env._parse_memory("invalid")

    with pytest.raises(ValueError, match="Invalid memory format"):
      env._parse_memory("1.2.3g")

    with pytest.raises(ValueError, match="Invalid memory format"):
      env._parse_memory("abc123")

    with pytest.raises(ValueError, match="Invalid memory format"):
      env._parse_memory("")

  def test_parse_memory_invalid_suffix(self):
    """Test that invalid memory suffixes raise ValueError"""
    env = Environment(name="test", base_image="alpine")

    with pytest.raises(ValueError, match="Invalid memory suffix"):
      env._parse_memory("1x")

    with pytest.raises(ValueError, match="Invalid memory suffix"):
      env._parse_memory("512pb")

    with pytest.raises(ValueError, match="Invalid memory suffix"):
      env._parse_memory("1kib")

  def test_memory_validation_in_constructor(self):
    """Test that memory is validated during environment creation"""
    # Valid memory formats should work
    env = Environment(name="test", base_image="alpine", memory="512m")
    assert env.memory == "512m"

    # Invalid memory formats should raise ValueError
    with pytest.raises(ValueError, match="Invalid memory format"):
      Environment(name="test", base_image="alpine", memory="invalid")


class TestEnvironmentCPUValidation:
  """Test CPU limit validation"""

  def test_cpu_validation_valid_values(self):
    """Test that valid CPU values are accepted"""
    # Positive values should work
    env = Environment(name="test", base_image="alpine", cpus=1.0)
    assert env.cpus == 1.0

    env = Environment(name="test", base_image="alpine", cpus=2.5)
    assert env.cpus == 2.5

    env = Environment(name="test", base_image="alpine", cpus=0.5)
    assert env.cpus == 0.5

    # None should work (no limit)
    env = Environment(name="test", base_image="alpine", cpus=None)
    assert env.cpus is None

  def test_cpu_validation_invalid_values(self):
    """Test that invalid CPU values raise ValueError"""
    with pytest.raises(ValueError, match="Invalid CPU limit"):
      Environment(name="test", base_image="alpine", cpus=0)

    with pytest.raises(ValueError, match="Invalid CPU limit"):
      Environment(name="test", base_image="alpine", cpus=-1.0)

    with pytest.raises(ValueError, match="Invalid CPU limit"):
      Environment(name="test", base_image="alpine", cpus=-0.5)

  def test_cpu_validation_edge_cases(self):
    """Test CPU validation edge cases"""
    # Very small positive value should work
    env = Environment(name="test", base_image="alpine", cpus=0.1)
    assert env.cpus == 0.1

    # Very large value should work
    env = Environment(name="test", base_image="alpine", cpus=100.0)
    assert env.cpus == 100.0


class TestPidsLimitValidation:
  """Test PID limit validation"""

  def test_pids_limit_valid_values(self):
    """Test that valid PID limits are accepted"""
    env = Environment(name="test", base_image="alpine", pids_limit=500)
    assert env.pids_limit == 500

    env = Environment(name="test", base_image="alpine", pids_limit=2000)
    assert env.pids_limit == 2000

  def test_pids_limit_invalid_values(self):
    """Test that invalid PID limits raise ValueError"""
    with pytest.raises(ValueError, match="Invalid PID limit"):
      Environment(name="test", base_image="alpine", pids_limit=0)

    with pytest.raises(ValueError, match="Invalid PID limit"):
      Environment(name="test", base_image="alpine", pids_limit=-1)


class TestUserFormatValidation:
  """Test user format validation"""

  def test_user_format_valid(self):
    """Test valid user formats"""
    # Default user should work
    env = Environment(name="test", base_image="alpine")
    assert env.user == "1000:1000"

    # Custom user:group should work
    env = Environment(name="test", base_image="alpine", user="1001:1001")
    assert env.user == "1001:1001"

    # Username:groupname should work
    env = Environment(name="test", base_image="alpine", user="dev:dev")
    assert env.user == "dev:dev"

    # Single username should work
    env = Environment(name="test", base_image="alpine", user="root")
    assert env.user == "root"

  def test_user_format_invalid(self):
    """Test invalid user formats"""
    with pytest.raises(ValueError, match="Invalid user format"):
      Environment(name="test", base_image="alpine", user="1000:1000:extra")


class TestSecurityLevelPresets:
  """Test security level preset application"""

  def test_security_level_relaxed(self):
    """Test RELAXED security preset"""
    env = Environment(name="test", base_image="alpine", security_level=SecurityLevel.RELAXED)

    assert env.user == "root"
    assert env.drop_capabilities == []
    assert env.no_new_privileges is False

  def test_security_level_standard(self):
    """Test STANDARD security preset"""
    env = Environment(name="test", base_image="alpine", security_level=SecurityLevel.STANDARD)

    assert env.user == "1000:1000"
    assert env.drop_capabilities == ["ALL"]
    assert env.no_new_privileges is True

  def test_security_level_none(self):
    """Test no security preset uses defaults"""
    env = Environment(name="test", base_image="alpine")

    # Should use default values
    assert env.user == "1000:1000"
    assert env.drop_capabilities == ["ALL"]
    assert env.no_new_privileges is True


class TestDockerHostConfig:
  """Test conversion to Docker host config"""

  def test_to_docker_host_config_memory(self):
    """Test memory conversion to Docker format"""
    env = Environment(name="test", base_image="alpine", memory="512m")
    config = env.to_docker_host_config()

    assert "Memory" in config
    assert config["Memory"] == 512 * 1024 * 1024

  def test_to_docker_host_config_cpu(self):
    """Test CPU conversion to Docker format"""
    env = Environment(name="test", base_image="alpine", cpus=1.5)
    config = env.to_docker_host_config()

    assert "CpuQuota" in config
    assert "CpuPeriod" in config
    assert config["CpuQuota"] == 150000  # 1.5 * 100000
    assert config["CpuPeriod"] == 100000

  def test_to_docker_host_config_pids(self):
    """Test PID limit conversion to Docker format"""
    env = Environment(name="test", base_image="alpine", pids_limit=500)
    config = env.to_docker_host_config()

    assert "PidsLimit" in config
    assert config["PidsLimit"] == 500

  def test_to_docker_host_config_none_values(self):
    """Test that None values are not included in config"""
    env = Environment(name="test", base_image="alpine", memory=None, cpus=None)
    config = env.to_docker_host_config()

    assert "Memory" not in config
    assert "CpuQuota" not in config
    assert "CpuPeriod" not in config
