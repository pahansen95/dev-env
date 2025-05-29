"""Configuration system using dataclasses"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import importlib.util
import sys


@dataclass
class VolumeMount:
  """Volume mount configuration"""

  source: str
  target: str
  mode: str = "rw"
  type: str = "bind"  # "bind" or "named"
  name: Optional[str] = None

  def __post_init__(self):
    if self.type == "named" and not self.name:
      self.name = self.source
    if self.type not in ("bind", "named"):
      raise ValueError(f"Invalid volume type: {self.type}")
    if self.mode not in ("rw", "ro"):
      raise ValueError(f"Invalid volume mode: {self.mode}")


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
  authorized_keys: List[str] = field(default_factory=list)
  password_auth: bool = False

  def __post_init__(self):
    if self.port < 1 or self.port > 65535:
      raise ValueError(f"Invalid SSH port: {self.port}")


@dataclass
class Environment:
  """Development environment configuration"""

  name: str
  base_image: str
  command: Optional[List[str]] = None
  environment: Optional[Dict[str, str]] = None
  volumes: Optional[List[VolumeMount]] = None
  ports: Optional[Dict[int, Any]] = None
  git: Optional[GitConfig] = None
  ssh: Optional[SSHConfig] = None
  labels: Optional[Dict[str, str]] = None

  def __post_init__(self):
    if not self.name:
      raise ValueError("Environment name is required")
    if not self.base_image:
      raise ValueError("Base image is required")

    # Add SSH port mapping if SSH is configured
    if self.ssh:
      if self.ports is None:
        self.ports = {}
      if 22 not in self.ports:
        self.ports[22] = {"HostPort": self.ssh.port}

  def to_dict(self) -> Dict[str, Any]:
    """Convert to dictionary for serialization"""
    return asdict(self)

  @classmethod
  def from_dict(cls, data: Dict[str, Any]) -> "Environment":
    """Create from dictionary"""
    # Convert nested dataclasses
    if "volumes" in data and data["volumes"]:
      data["volumes"] = [VolumeMount(**v) if isinstance(v, dict) else v for v in data["volumes"]]
    if "git" in data and data["git"]:
      data["git"] = GitConfig(**data["git"]) if isinstance(data["git"], dict) else data["git"]
    if "ssh" in data and data["ssh"]:
      data["ssh"] = SSHConfig(**data["ssh"]) if isinstance(data["ssh"], dict) else data["ssh"]

    return cls(**data)


def load_environment(config_path: Path) -> Environment:
  """Load environment configuration from file"""
  if not config_path.exists():
    raise FileNotFoundError(f"Configuration file not found: {config_path}")

  if config_path.suffix == ".json":
    # Load JSON configuration
    with open(config_path) as f:
      data = json.load(f)
    return Environment.from_dict(data)

  elif config_path.suffix == ".py":
    # Load Python configuration
    spec = importlib.util.spec_from_file_location("config", config_path)
    if not spec or not spec.loader:
      raise ImportError(f"Cannot load Python config: {config_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["config"] = module
    spec.loader.exec_module(module)

    # Look for environment definition
    if hasattr(module, "environment"):
      env = module.environment
      if isinstance(env, dict):
        return Environment.from_dict(env)
      elif isinstance(env, Environment):
        return env
      else:
        raise ValueError("'environment' must be a dict or Environment instance")

    # Look for a function that returns environment
    elif hasattr(module, "get_environment"):
      env = module.get_environment()
      if isinstance(env, dict):
        return Environment.from_dict(env)
      elif isinstance(env, Environment):
        return env
      else:
        raise ValueError("get_environment() must return a dict or Environment instance")

    else:
      raise ValueError("Config must define 'environment' or 'get_environment()'")

  else:
    raise ValueError(f"Unsupported configuration format: {config_path.suffix}")


# Standard environment templates


def python_environment(name: str, version: str = "3.11", **kwargs) -> Environment:
  """Create a Python development environment"""
  return Environment(
    name=name,
    base_image=f"python:{version}-slim",
    environment={"PYTHONUNBUFFERED": "1", "PIP_NO_CACHE_DIR": "1"},
    volumes=[
      VolumeMount(source=".", target="/workspace", mode="rw"),
      VolumeMount(source=f"{name}-cache", target="/root/.cache", type="named"),
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
      VolumeMount(source=f"{name}-modules", target="/workspace/node_modules", type="named"),
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
