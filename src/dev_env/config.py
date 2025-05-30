"""Configuration system using dataclasses"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from enum import Enum
import importlib.util
import sys


@dataclass
class VolumeMount:
  """Volume mount configuration"""

  source: str
  target: str
  mode: str = "rw"
  name: str | None = None

  def __post_init__(self):
    # Validate mode
    if self.mode not in ("rw", "ro"):
      raise ValueError(f"Invalid volume mode: {self.mode}")

    # Auto-assign name for named volumes
    if self.is_named_volume() and not self.name:
      self.name = self.source

  def is_named_volume(self) -> bool:
    """Check if this is a named volume (not an absolute path)"""
    from pathlib import Path

    return not Path(self.source).is_absolute()

  @property
  def type(self) -> str:
    """Get volume type (bind or named) based on source path"""
    return "named" if self.is_named_volume() else "bind"


@dataclass
class GitConfig:
  """Git repository configuration"""

  url: str
  branch: str = "main"
  path: str = "/workspace"
  shallow: bool = True

  def __post_init__(self):
    if not self.url:
      raise ValueError("Git URL is required")


@dataclass
class SSHConfig:
  """SSH configuration"""

  port: int = 22
  authorized_keys: list[str] = field(default_factory=list)
  password_auth: bool = False

  def __post_init__(self):
    if self.port < 1 or self.port > 65535:
      raise ValueError(f"Invalid SSH port: {self.port}")


@dataclass
class NetworkConfig:
  """Network configuration"""

  name: str | None = None
  driver: str = "bridge"
  options: dict[str, str] | None = None
  labels: dict[str, str] | None = None

  def __post_init__(self):
    if self.driver not in ("bridge", "host", "none", "overlay", "macvlan"):
      raise ValueError(f"Invalid network driver: {self.driver}")


class SecurityLevel(Enum):
  """Security preset levels"""

  RELAXED = "relaxed"  # Compatibility mode
  STANDARD = "standard"  # Recommended defaults


@dataclass
class Environment:
  """Development environment configuration"""

  name: str
  base_image: str
  command: list[str] | None = None
  environment: dict[str, str] | None = None
  volumes: list[VolumeMount] | None = None
  ports: dict[int, Any] | None = None
  git: GitConfig | None = None
  ssh: SSHConfig | None = None
  network: NetworkConfig | None = None
  labels: dict[str, str] | None = None

  # Security configuration (formerly SecurityConfig)
  user: str = "1000:1000"
  drop_capabilities: list[str] = field(default_factory=lambda: ["ALL"])
  add_capabilities: list[str] = field(default_factory=list)
  no_new_privileges: bool = True
  read_only_root_fs: bool = False

  # Resource configuration (formerly ResourceConfig)
  memory: str | None = "2g"
  cpus: float | None = 2.0
  pids_limit: int = 1000

  # Security preset level
  security_level: SecurityLevel | None = None

  def __post_init__(self):
    if not self.name:
      raise ValueError("Environment name is required")
    if not self.base_image:
      raise ValueError("Base image is required")

    # Apply security preset if specified
    if self.security_level:
      if self.security_level == SecurityLevel.RELAXED:
        self.user = "root"
        self.drop_capabilities = []
        self.no_new_privileges = False
      elif self.security_level == SecurityLevel.STANDARD:
        self.user = "1000:1000"
        self.drop_capabilities = ["ALL"]
        self.no_new_privileges = True

    # Validate user format
    if self.user and ":" in self.user:
      parts = self.user.split(":")
      if len(parts) > 2:
        raise ValueError(f"Invalid user format: {self.user}. Expected 'uid:gid' or 'username:groupname'")

    # Validate memory format
    if self.memory:
      self._parse_memory(self.memory)

    # Validate CPU limits
    if self.cpus is not None and self.cpus <= 0:
      raise ValueError(f"Invalid CPU limit: {self.cpus}")

    if self.pids_limit <= 0:
      raise ValueError(f"Invalid PID limit: {self.pids_limit}")

    # Add SSH port mapping if SSH is configured
    if self.ssh:
      if self.ports is None:
        self.ports = {}
      if 22 not in self.ports:
        self.ports[22] = {"HostPort": self.ssh.port}

  def _parse_memory(self, memory: str) -> int:
    """Parse memory string to bytes"""
    memory = memory.lower().strip()

    multipliers = {
      "b": 1,
      "k": 1024,
      "kb": 1024,
      "m": 1024**2,
      "mb": 1024**2,
      "g": 1024**3,
      "gb": 1024**3,
      "t": 1024**4,
      "tb": 1024**4,
    }

    # Extract numeric part and suffix
    import re

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([a-z]*)$", memory)
    if not match:
      raise ValueError(f"Invalid memory format: {memory}")

    number, suffix = match.groups()
    number = float(number)

    # Empty suffix defaults to bytes
    if not suffix:
      suffix = "b"

    if suffix not in multipliers:
      raise ValueError(f"Invalid memory suffix: {suffix}")

    return int(number * multipliers[suffix])

  def to_docker_host_config(self) -> dict[str, Any]:
    """Convert resource constraints to Docker host config format"""
    config = {}

    if self.memory:
      config["Memory"] = self._parse_memory(self.memory)

    if self.cpus is not None:
      config["CpuQuota"] = int(self.cpus * 100000)
      config["CpuPeriod"] = 100000

    if self.pids_limit:
      config["PidsLimit"] = self.pids_limit

    return config


def load_environment(config_path: Path) -> Environment:
  """Load environment configuration from Python file"""
  if not config_path.exists():
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

  if config_path.suffix != ".py":
    raise ValueError(f"Only Python configuration files (.py) are supported, got: {config_path.suffix}")

  # Load Python configuration
  spec = importlib.util.spec_from_file_location("config", config_path)
  if not spec or not spec.loader:
    raise ImportError(f"Cannot load Python config: {config_path}")

  module = importlib.util.module_from_spec(spec)
  sys.modules["config"] = module
  spec.loader.exec_module(module)

  # Look for 'config' variable (standard convention)
  if hasattr(module, "config"):
    config = module.config
    if isinstance(config, Environment):
      return config
    else:
      raise ValueError("'config' variable must be an Environment instance")

  # Look for legacy 'environment' variable
  elif hasattr(module, "environment"):
    env = module.environment
    if isinstance(env, Environment):
      return env
    else:
      raise ValueError("'environment' variable must be an Environment instance")

  # Look for a function that returns environment
  elif hasattr(module, "get_environment"):
    env = module.get_environment()
    if isinstance(env, Environment):
      return env
    else:
      raise ValueError("get_environment() must return an Environment instance")

  else:
    raise ValueError("Config must define 'config', 'environment', or 'get_environment()'")


# Standard environment templates


def python_environment(name: str, version: str = "3.11", **kwargs) -> Environment:
  """Create a Python development environment"""
  return Environment(
    name=name,
    base_image=f"python:{version}-slim",
    environment={"PYTHONUNBUFFERED": "1", "PIP_NO_CACHE_DIR": "1"},
    volumes=[
      VolumeMount(source=".", target="/workspace", mode="rw"),
      VolumeMount(source=f"{name}-cache", target="/root/.cache"),
    ],
    command=["/bin/bash"],
    **kwargs,
  )


def node_environment(name: str, version: str = "18", **kwargs) -> Environment:
  """Create a Node.js development environment"""
  return Environment(
    name=name,
    base_image=f"node:{version}-slim",
    environment={"NODE_ENV": "development"},
    volumes=[
      VolumeMount(source=".", target="/workspace", mode="rw"),
      VolumeMount(source=f"{name}-modules", target="/workspace/node_modules"),
    ],
    command=["/bin/bash"],
    **kwargs,
  )


def ubuntu_environment(name: str, version: str = "22.04", **kwargs) -> Environment:
  """Create an Ubuntu development environment"""
  return Environment(
    name=name,
    base_image=f"ubuntu:{version}",
    volumes=[VolumeMount(source=".", target="/workspace", mode="rw")],
    command=["/bin/bash"],
    **kwargs,
  )
