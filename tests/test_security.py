"""Security-related tests for dev-env"""

import pytest
from dev_env.config import Environment, SecurityConfig, ResourceConfig, SecurityLevel, SECURITY_PRESETS, VolumeMount
from dev_env.utils import (
  SecurityError,
  validate_volume_security,
  validate_port_security,
  apply_security_defaults,
  FORBIDDEN_MOUNT_PATHS,
)


class TestSecurityConfig:
  """Test SecurityConfig dataclass"""

  def test_default_security_config(self):
    """Verify default security configuration"""
    config = SecurityConfig()
    assert config.user == "1000:1000"
    assert config.drop_capabilities == ["ALL"]
    assert config.add_capabilities == []
    assert config.no_new_privileges is True
    assert config.read_only_root_fs is False

  def test_security_config_user_validation(self):
    """Test user format validation"""
    # Valid user formats
    SecurityConfig(user="1000:1000")
    SecurityConfig(user="root")
    SecurityConfig(user="nobody:nogroup")

    # Invalid user format should raise ValueError
    with pytest.raises(ValueError, match="Invalid user format"):
      SecurityConfig(user="invalid:format:extra:parts")

  def test_security_config_custom_values(self):
    """Test custom security configuration"""
    config = SecurityConfig(
      user="root",
      drop_capabilities=["NET_RAW"],
      add_capabilities=["SYS_TIME"],
      no_new_privileges=False,
      read_only_root_fs=True,
    )
    assert config.user == "root"
    assert config.drop_capabilities == ["NET_RAW"]
    assert config.add_capabilities == ["SYS_TIME"]
    assert config.no_new_privileges is False
    assert config.read_only_root_fs is True


class TestResourceConfig:
  """Test ResourceConfig dataclass"""

  def test_default_resource_config(self):
    """Verify default resource configuration"""
    config = ResourceConfig()
    assert config.memory == "2g"
    assert config.cpus == 2.0
    assert config.pids_limit == 1000

  def test_memory_parsing(self):
    """Test memory string parsing"""
    config = ResourceConfig(memory="512m")
    assert config._parse_memory("512m") == 512 * 1024 * 1024

    config = ResourceConfig(memory="1g")
    assert config._parse_memory("1g") == 1024 * 1024 * 1024

    config = ResourceConfig(memory="2048")
    assert config._parse_memory("2048") == 2048

  def test_invalid_memory_format(self):
    """Test invalid memory format handling"""
    with pytest.raises(ValueError, match="Invalid memory format"):
      ResourceConfig(memory="invalid")

    with pytest.raises(ValueError, match="Invalid memory suffix"):
      ResourceConfig(memory="100invalid")

  def test_invalid_cpu_limit(self):
    """Test invalid CPU limit handling"""
    with pytest.raises(ValueError, match="Invalid CPU limit"):
      ResourceConfig(cpus=-1.0)

    with pytest.raises(ValueError, match="Invalid CPU limit"):
      ResourceConfig(cpus=0)

  def test_invalid_pids_limit(self):
    """Test invalid PID limit handling"""
    with pytest.raises(ValueError, match="Invalid PID limit"):
      ResourceConfig(pids_limit=0)

    with pytest.raises(ValueError, match="Invalid PID limit"):
      ResourceConfig(pids_limit=-100)

  def test_to_docker_config(self):
    """Test conversion to Docker configuration"""
    config = ResourceConfig(memory="1g", cpus=1.5, pids_limit=500)
    docker_config = config.to_docker_config()

    assert docker_config["Memory"] == 1024 * 1024 * 1024
    assert docker_config["CpuQuota"] == 150000
    assert docker_config["CpuPeriod"] == 100000
    assert docker_config["PidsLimit"] == 500


class TestSecurityPresets:
  """Test security preset levels"""

  def test_relaxed_preset(self):
    """Test relaxed security preset"""
    config = SECURITY_PRESETS[SecurityLevel.RELAXED]
    assert config.user == "root"
    assert config.drop_capabilities == []
    assert config.no_new_privileges is False

  def test_standard_preset(self):
    """Test standard security preset"""
    config = SECURITY_PRESETS[SecurityLevel.STANDARD]
    assert config.user == "1000:1000"
    assert config.drop_capabilities == ["ALL"]
    assert config.no_new_privileges is True


class TestEnvironmentSecurity:
  """Test Environment security integration"""

  def test_environment_default_security(self):
    """Test that Environment applies default security"""
    env = Environment(name="test", base_image="alpine")
    assert env.security is not None
    assert env.security.user == "1000:1000"
    assert env.resources is not None
    assert env.resources.memory == "2g"

  def test_environment_security_preset(self):
    """Test security preset application"""
    env = Environment(name="test", base_image="alpine", security_level=SecurityLevel.RELAXED)
    assert env.security.user == "root"
    assert env.security.drop_capabilities == []

  def test_environment_custom_security(self):
    """Test custom security configuration"""
    custom_security = SecurityConfig(user="dev:dev")
    env = Environment(name="test", base_image="alpine", security=custom_security)
    assert env.security.user == "dev:dev"


class TestVolumeSecurityValidation:
  """Test volume mount security validation"""

  def test_safe_volume_mounts(self):
    """Test that safe volume mounts pass validation"""
    safe_volumes = [
      VolumeMount(source="./workspace", target="/app"),
      VolumeMount(source="my-volume", target="/vol", type="named"),
    ]

    # Should not raise any exceptions
    validate_volume_security(safe_volumes)

  @pytest.mark.parametrize("forbidden_path", FORBIDDEN_MOUNT_PATHS)
  def test_forbidden_volume_mounts(self, forbidden_path):
    """Test that forbidden paths are rejected"""
    dangerous_volumes = [VolumeMount(source=forbidden_path, target="/mounted")]

    with pytest.raises(SecurityError, match="security violation"):
      validate_volume_security(dangerous_volumes)

  def test_subdirectory_forbidden_mounts(self):
    """Test that subdirectories of forbidden paths are also rejected"""
    dangerous_volumes = [
      VolumeMount(source="/etc/passwd", target="/passwd"),
      VolumeMount(source="/proc/version", target="/version"),
    ]

    for volume in [[vol] for vol in dangerous_volumes]:
      with pytest.raises(SecurityError, match="security violation"):
        validate_volume_security(volume)

  def test_empty_volume_list(self):
    """Test that empty volume list passes validation"""
    validate_volume_security([])
    validate_volume_security(None)


class TestPortSecurityValidation:
  """Test port mapping security validation"""

  def test_safe_port_mappings(self):
    """Test that safe port mappings pass validation"""
    safe_ports = {80: {"HostPort": 8080, "HostIp": "127.0.0.1"}, 443: {"HostPort": 8443, "HostIp": "192.168.1.100"}}

    # Should not raise any exceptions
    validate_port_security(safe_ports)

  def test_dangerous_port_mappings(self):
    """Test that dangerous port mappings are rejected"""
    dangerous_ports = {80: {"HostPort": 8080, "HostIp": "0.0.0.0"}}

    with pytest.raises(SecurityError, match="cannot bind to all interfaces"):
      validate_port_security(dangerous_ports)

  def test_default_localhost_binding(self):
    """Test that missing HostIp defaults to localhost"""
    ports = {80: {"HostPort": 8080}}

    validate_port_security(ports)
    assert ports[80]["HostIp"] == "127.0.0.1"

  def test_empty_port_mappings(self):
    """Test that empty port mappings pass validation"""
    validate_port_security({})
    validate_port_security(None)


class TestSecurityDefaults:
  """Test apply_security_defaults function"""

  def test_apply_security_defaults(self):
    """Test that security defaults are properly applied"""
    env = Environment(name="test", base_image="alpine")
    # Remove defaults to test application
    env.security = None
    env.resources = None

    apply_security_defaults(env)

    assert env.security is not None
    assert env.resources is not None

  def test_security_validation_integration(self):
    """Test that security validation catches issues"""
    env = Environment(
      name="test",
      base_image="alpine",
      volumes=[VolumeMount(source="/etc", target="/mounted")],
      ports={80: {"HostIp": "0.0.0.0", "HostPort": 8080}},
    )

    with pytest.raises(SecurityError):
      apply_security_defaults(env)


class TestSecurityError:
  """Test SecurityError exception"""

  def test_security_error_format(self):
    """Test SecurityError formatting"""
    error = SecurityError("Test security violation")
    formatted = error.format_error()

    assert "Error: Test security violation" in formatted
    assert "docs/security.md" in formatted
    assert error.exit_code == 2

  def test_security_error_inheritance(self):
    """Test that SecurityError inherits from DevEnvError"""
    from dev_env.utils import DevEnvError

    error = SecurityError("Test")
    assert isinstance(error, DevEnvError)


class TestSecurityIntegration:
  """Integration tests for security features"""

  def test_secure_environment_creation(self):
    """Test creating a secure environment configuration"""
    env = Environment(
      name="secure-test",
      base_image="python:3.13-slim",
      volumes=[VolumeMount(source="./app", target="/workspace")],
      ports={8000: {"HostPort": 8000, "HostIp": "127.0.0.1"}},
      security=SecurityConfig(
        user="1000:1000", drop_capabilities=["ALL"], add_capabilities=["CHOWN"], no_new_privileges=True
      ),
      resources=ResourceConfig(memory="1g", cpus=1.0, pids_limit=100),
    )

    # Should not raise any exceptions
    apply_security_defaults(env)

    assert env.security.user == "1000:1000"
    assert "ALL" in env.security.drop_capabilities
    assert "CHOWN" in env.security.add_capabilities
    assert env.resources.memory == "1g"

  def test_relaxed_environment_creation(self):
    """Test creating a relaxed environment for compatibility"""
    env = Environment(
      name="legacy-test",
      base_image="ubuntu:20.04",
      security_level=SecurityLevel.RELAXED,
      volumes=[VolumeMount(source="./legacy", target="/app")],
    )

    apply_security_defaults(env)

    assert env.security.user == "root"
    assert env.security.drop_capabilities == []
    assert env.security.no_new_privileges is False
