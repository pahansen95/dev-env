"""Example Node.js development environment configuration"""

from dev_env.config import Environment, VolumeMount, SSHConfig

# Node.js development environment
environment = Environment(
  name="node-dev",
  base_image="node:18-slim",
  command=["/bin/bash"],
  environment={
    "NODE_ENV": "development",
  },
  volumes=[
    VolumeMount(source=".", target="/workspace", mode="rw"),
    VolumeMount(source="node-modules", target="/workspace/node_modules", type="named"),
  ],
  ssh=SSHConfig(port=2223),
)
