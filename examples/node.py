#!/usr/bin/env python3
"""
Node.js Development Environment

This example provides a Node.js development setup with:
- Node.js 20 LTS with npm and yarn
- Project code mounted at /workspace
- Common development tools
- Port forwarding for web applications

Usage:
  # Basic Node.js development
  dev-env run examples/node.py

  # With port forwarding for web app
  dev-env run examples/node.py -p 3000:3000
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount

# Get current directory for mounting
current_dir = Path.cwd()

# Node.js development environment
environment = Environment(
  name="node-dev",
  base_image="node:20-slim",
  volumes=[
    # Mount current directory as workspace
    VolumeMount(source=str(current_dir), target="/workspace", mode="rw"),
    # Persist npm/yarn cache between sessions
    VolumeMount(source="npm-cache", target="/root/.npm", mode="rw"),
    VolumeMount(source="yarn-cache", target="/usr/local/share/.cache/yarn", mode="rw"),
  ],
  working_dir="/workspace",
  command=["/bin/bash"],
  # Common ports for Node.js applications
  ports=["3000:3000", "3001:3001", "8080:8080"],
  environment={"NODE_ENV": "development", "NPM_CONFIG_LOGLEVEL": "warn", "NODE_OPTIONS": "--max-old-space-size=4096"},
  init_commands=[
    # Install system utilities
    "apt-get update && apt-get install -y git curl vim build-essential python3",
    # Install global npm packages for development
    "npm install -g yarn pnpm nodemon ts-node typescript",
    "npm install -g eslint prettier jest",
    # Install project dependencies if package.json exists
    "[ -f package.json ] && npm install || true",
    # Create .env file if .env.example exists
    "[ -f .env.example ] && [ ! -f .env ] && cp .env.example .env || true",
    # Show Node.js and npm versions
    "echo 'Node.js version:' && node --version",
    "echo 'npm version:' && npm --version",
    "echo 'yarn version:' && yarn --version",
  ],
)
