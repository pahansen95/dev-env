"""Example Python development environment configuration"""

from dev_env.config import Environment, VolumeMount, SSHConfig

# Simple Python environment
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
    VolumeMount(source="python-cache", target="/root/.cache", type="named"),
  ],
  ssh=SSHConfig(port=2222),
)
