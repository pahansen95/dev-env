"""Secure Node.js development environment with security features"""

from dev_env.config import Environment, VolumeMount, SSHConfig, SecurityConfig, ResourceConfig, GitConfig

# Secure Node.js environment with Git integration
environment = Environment(
  name="node-secure",
  base_image="node:18-slim",
  command=["/bin/bash"],
  # Environment variables
  environment={
    "NODE_ENV": "development",
    "NPM_CONFIG_CACHE": "/home/node/.npm",
  },
  # Volume mounts - secure configuration
  volumes=[
    VolumeMount(source="./app", target="/workspace", mode="rw"),
    VolumeMount(source="node-modules", target="/workspace/node_modules", type="named"),
    VolumeMount(source="npm-cache", target="/home/node/.npm", type="named"),
  ],
  # Port mappings - localhost binding for security
  ports={
    22: {"HostPort": 2225, "HostIp": "127.0.0.1"},  # SSH
    3000: {"HostPort": 3001, "HostIp": "127.0.0.1"},  # React dev server
    8080: {"HostPort": 8081, "HostIp": "127.0.0.1"},  # Backend API
  },
  # SSH configuration
  ssh=SSHConfig(port=22, password_auth=False),
  # Git repository (example Node.js project)
  git=GitConfig(
    url="https://github.com/nodejs/node.git",
    branch="main",
    path="/workspace",
    shallow=True,
  ),
  # Security configuration - run as node user (uid 1000)
  security=SecurityConfig(
    user="1000:1000",  # Use node user
    drop_capabilities=["ALL"],  # Drop all capabilities
    add_capabilities=["CHOWN", "SETGID"],  # Only necessary capabilities
    no_new_privileges=True,  # Prevent privilege escalation
    read_only_root_fs=False,  # Allow writes for npm installs
  ),
  # Resource constraints appropriate for Node.js development
  resources=ResourceConfig(
    memory="2g",  # Sufficient for Node.js + npm
    cpus=2.0,  # Good for parallel builds
    pids_limit=1000,  # Handle npm spawned processes
  ),
)
