"""Tests for configuration loading and validation"""

import json
import pytest

from dev_env.config import (
  Environment,
  VolumeConfig,
  GitConfig,
  NetworkConfig,
  load_environment,
  parse_port_mapping,
  parse_volume_mapping,
)


class TestEnvironmentConfig:
  """Test Environment dataclass configuration"""

  def test_minimal_environment(self):
    """Test creating environment with minimal required fields"""
    env = Environment(name="test", base_image="python:3.13")
    assert env.name == "test"
    assert env.base_image == "python:3.13"
    assert env.command is None
    assert env.ports == {}
    assert env.environment == {}
    assert env.volumes == []

  def test_full_environment(self, sample_environment):
    """Test creating environment with all fields"""
    env = sample_environment
    assert env.name == "test-env"
    assert env.base_image == "python:3.13"
    assert env.command == ["sleep", "infinity"]
    assert env.ports == {22: 2222, 8000: 8000}
    assert env.environment == {"TEST_VAR": "test_value"}
    assert len(env.volumes) == 2
    assert env.network.name == "test-network"
    assert env.git.url == "https://github.com/test/repo.git"

  def test_environment_validation_missing_name(self):
    """Test validation fails when name is missing"""
    with pytest.raises(TypeError):
      Environment(base_image="python:3.13")

  def test_environment_validation_missing_base_image(self):
    """Test validation fails when base_image is missing"""
    with pytest.raises(TypeError):
      Environment(name="test")

  def test_environment_to_dict(self, sample_environment):
    """Test converting environment to dictionary"""
    env_dict = sample_environment.to_dict()
    assert env_dict["name"] == "test-env"
    assert env_dict["base_image"] == "python:3.13"
    assert env_dict["command"] == ["sleep", "infinity"]
    assert isinstance(env_dict["volumes"], list)
    assert isinstance(env_dict["network"], dict)
    assert isinstance(env_dict["git"], dict)


class TestVolumeConfig:
  """Test VolumeConfig dataclass"""

  def test_named_volume(self):
    """Test named volume configuration"""
    vol = VolumeConfig(name="data", source="data-vol", target="/data", type="named")
    assert vol.name == "data"
    assert vol.source == "data-vol"
    assert vol.target == "/data"
    assert vol.type == "named"
    assert vol.mode == "rw"

  def test_bind_volume(self):
    """Test bind mount configuration"""
    vol = VolumeConfig(name="bind", source="/host/path", target="/container/path", type="bind", mode="ro")
    assert vol.type == "bind"
    assert vol.mode == "ro"

  def test_volume_validation_post_init(self):
    """Test volume validation in __post_init__"""
    # Valid named volume
    vol = VolumeConfig(name="test", source="vol", target="/data", type="named")
    assert vol.name == "test"

    # Valid bind mount
    vol = VolumeConfig(name="bind", source="/tmp", target="/tmp", type="bind")
    assert vol.name == "bind"


class TestGitConfig:
  """Test GitConfig dataclass"""

  def test_git_config_minimal(self):
    """Test minimal git configuration"""
    git = GitConfig(url="https://github.com/user/repo.git")
    assert git.url == "https://github.com/user/repo.git"
    assert git.branch == "main"
    assert git.path == "/workspace"

  def test_git_config_full(self):
    """Test full git configuration"""
    git = GitConfig(url="https://github.com/user/repo.git", branch="develop", path="/code")
    assert git.branch == "develop"
    assert git.path == "/code"


class TestNetworkConfig:
  """Test NetworkConfig dataclass"""

  def test_network_config_minimal(self):
    """Test minimal network configuration"""
    net = NetworkConfig()
    assert net.name is None
    assert net.driver == "bridge"
    assert net.options is None
    assert net.labels is None

  def test_network_config_full(self):
    """Test full network configuration"""
    net = NetworkConfig(
      name="custom-net", driver="overlay", options={"subnet": "172.20.0.0/16"}, labels={"env": "test"}
    )
    assert net.name == "custom-net"
    assert net.driver == "overlay"
    assert net.options["subnet"] == "172.20.0.0/16"
    assert net.labels["env"] == "test"


class TestConfigurationLoading:
  """Test configuration file loading"""

  def test_load_python_config(self, sample_config_file):
    """Test loading Python configuration file"""
    env = load_environment(sample_config_file)
    assert env.name == "test-env"
    assert env.base_image == "python:3.13"
    assert len(env.volumes) == 2
    assert env.network.name == "test-network"

  def test_load_json_config(self, sample_json_config):
    """Test loading JSON configuration file"""
    env = load_environment(sample_json_config)
    assert env.name == "json-env"
    assert env.base_image == "ubuntu:22.04"
    assert env.command == ["bash", "-c", "sleep infinity"]
    assert env.ports == {"80": 8080}

  def test_load_nonexistent_file(self, temp_dir):
    """Test loading non-existent configuration file"""
    nonexistent = temp_dir / "nonexistent.py"
    with pytest.raises(FileNotFoundError):
      load_environment(nonexistent)

  def test_load_invalid_python_config(self, temp_dir):
    """Test loading invalid Python configuration"""
    invalid_config = temp_dir / "invalid.py"
    invalid_config.write_text("invalid python syntax {}")

    with pytest.raises(Exception):  # Could be SyntaxError or other
      load_environment(invalid_config)

  def test_load_invalid_json_config(self, temp_dir):
    """Test loading invalid JSON configuration"""
    invalid_config = temp_dir / "invalid.json"
    invalid_config.write_text('{"invalid": json}')

    with pytest.raises(json.JSONDecodeError):
      load_environment(invalid_config)

  def test_load_python_config_missing_config_var(self, temp_dir):
    """Test loading Python config without 'config' variable"""
    no_config = temp_dir / "no_config.py"
    no_config.write_text("x = 42")

    with pytest.raises(AttributeError, match="config"):
      load_environment(no_config)

  def test_load_unsupported_file_type(self, temp_dir):
    """Test loading unsupported file type"""
    unsupported = temp_dir / "config.yaml"
    unsupported.write_text("name: test")

    with pytest.raises(ValueError, match="Unsupported"):
      load_environment(unsupported)


class TestPortMapping:
  """Test port mapping parsing"""

  def test_parse_port_mapping_int_to_int(self):
    """Test parsing integer port to integer port"""
    result = parse_port_mapping({8080: 80})
    assert result == {8080: {"HostPort": "80"}}

  def test_parse_port_mapping_str_to_str(self):
    """Test parsing string port to string port"""
    result = parse_port_mapping({"8080": "80"})
    assert result == {"8080": {"HostPort": "80"}}

  def test_parse_port_mapping_int_to_str(self):
    """Test parsing integer port to string port"""
    result = parse_port_mapping({8080: "80"})
    assert result == {8080: {"HostPort": "80"}}

  def test_parse_port_mapping_complex(self):
    """Test parsing complex port mapping"""
    ports = {22: 2222, "80": "8080", 443: {"HostPort": "4443", "HostIp": "127.0.0.1"}}
    result = parse_port_mapping(ports)

    assert result[22] == {"HostPort": "2222"}
    assert result["80"] == {"HostPort": "8080"}
    assert result[443] == {"HostPort": "4443", "HostIp": "127.0.0.1"}

  def test_parse_port_mapping_empty(self):
    """Test parsing empty port mapping"""
    result = parse_port_mapping({})
    assert result == {}

  def test_parse_port_mapping_none(self):
    """Test parsing None port mapping"""
    result = parse_port_mapping(None)
    assert result == {}


class TestVolumeMapping:
  """Test volume mapping parsing"""

  def test_parse_volume_mapping_list(self):
    """Test parsing list of VolumeConfig objects"""
    volumes = [
      VolumeConfig(name="data", source="data-vol", target="/data", type="named"),
      VolumeConfig(name="bind", source="/tmp", target="/tmp", type="bind", mode="ro"),
    ]
    result = parse_volume_mapping(volumes)

    assert "data-vol" in result
    assert result["data-vol"] == {"bind": "/data", "mode": "rw"}
    assert "/tmp" in result
    assert result["/tmp"] == {"bind": "/tmp", "mode": "ro"}

  def test_parse_volume_mapping_empty(self):
    """Test parsing empty volume list"""
    result = parse_volume_mapping([])
    assert result == {}

  def test_parse_volume_mapping_none(self):
    """Test parsing None volume list"""
    result = parse_volume_mapping(None)
    assert result == {}

  def test_parse_volume_mapping_named_volume(self):
    """Test parsing named volume specifically"""
    volumes = [VolumeConfig(name="db", source="postgres-data", target="/var/lib/postgresql/data", type="named")]
    result = parse_volume_mapping(volumes)

    assert "postgres-data" in result
    assert result["postgres-data"]["bind"] == "/var/lib/postgresql/data"
    assert result["postgres-data"]["mode"] == "rw"

  def test_parse_volume_mapping_bind_mount(self):
    """Test parsing bind mount specifically"""
    volumes = [VolumeConfig(name="src", source="/host/src", target="/app", type="bind", mode="ro")]
    result = parse_volume_mapping(volumes)

    assert "/host/src" in result
    assert result["/host/src"]["bind"] == "/app"
    assert result["/host/src"]["mode"] == "ro"
