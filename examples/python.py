"""Example Python development environment configuration"""

from dev_env.config import Environment, VolumeMount, SSHConfig, SecurityLevel

# Simple Python environment with standard security
environment = Environment(
  name="python-dev",
  base_image="python:3.13-slim",
  command=["/bin/bash"],
  environment={
    "PYTHONUNBUFFERED": "1",
    "PIP_NO_CACHE_DIR": "1",
  },
  volumes=[
    VolumeMount(source=".", target="/workspace", mode="rw"),
    VolumeMount(source="python-cache", target="/home/dev/.cache", type="named"),  # Updated path for non-root
  ],
  ports={
    22: {"HostPort": 2222, "HostIp": "127.0.0.1"},  # Explicit localhost binding
  },
  ssh=SSHConfig(port=22, password_auth=False),
  security_level=SecurityLevel.STANDARD,  # Apply standard security defaults
)
