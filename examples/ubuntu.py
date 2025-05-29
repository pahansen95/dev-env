"""Example Ubuntu development environment configuration"""

from dev_env.config import Environment, VolumeMount, SSHConfig, GitConfig

# Ubuntu environment with Git repository
environment = Environment(
  name="ubuntu-dev",
  base_image="ubuntu:22.04",
  command=["/bin/bash"],
  volumes=[
    VolumeMount(source=".", target="/workspace", mode="rw"),
  ],
  git=GitConfig(
    url="https://github.com/example/repo.git",
    branch="main",
    path="/workspace/repo",
  ),
  ssh=SSHConfig(port=2224),
)
