#!/usr/bin/env python3
"""
Node.js Development Environment

This example provides a Node.js development setup with:
- Node.js 20 LTS with npm
- Project code mounted at /workspace
- Common web development ports
- Persistent npm/yarn cache

Usage:
  python -m dev_env up examples/node.py

After starting:
  python -m dev_env ssh node-dev
  # Install project dependencies:
  # npm install
  # npm run dev
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, SSHConfig

# Get current directory for mounting
current_dir = Path.cwd()

# Node.js development environment
config = Environment(
  name="node-dev",
  base_image="node:20-slim",
  command=["/bin/bash"],
  volumes=[
    # Mount current directory as workspace
    VolumeMount(source=str(current_dir), target="/workspace"),
    # Persist npm cache between sessions
    VolumeMount(source="npm-cache", target="/root/.npm"),
    # Persist global npm packages
    VolumeMount(source="npm-global", target="/usr/local/lib/node_modules"),
  ],
  # Common ports for Node.js applications
  ports={
    22: {"HostPort": 2225},  # SSH
    3000: {"HostPort": 3000},  # React/Next.js default
    3001: {"HostPort": 3001},  # Alternative port
    8080: {"HostPort": 8080},  # Alternative web port
    5173: {"HostPort": 5173},  # Vite default
  },
  # SSH configuration
  ssh=SSHConfig(port=22),
  environment={"NODE_ENV": "development", "NPM_CONFIG_LOGLEVEL": "warn", "NODE_OPTIONS": "--max-old-space-size=4096"},
  # Resource allocation
  memory="4g",  # Node.js can be memory intensive
  cpus=4.0,
)

# Note: After starting, you can install global tools:
# npm install -g yarn pnpm nodemon typescript ts-node
# npm install -g eslint prettier jest
