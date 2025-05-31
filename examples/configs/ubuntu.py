#!/usr/bin/env python3
"""
General Purpose Ubuntu Development Environment

This example provides a flexible Ubuntu environment for:
- General development and experimentation
- System administration tasks
- Multi-language development
- Tool installation and testing

Usage:
  python -m dev_env up examples/ubuntu.py

Notes:
  - SSH is enabled on port 2222
  - Common development ports are exposed
  - APT cache is persisted across restarts
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount, SSHConfig

# Get current directory
current_dir = Path.cwd()

# General purpose Ubuntu environment
config = Environment(
  name="ubuntu-dev",
  base_image="ubuntu:22.04",
  command=["/bin/bash"],
  volumes=[
    # Mount current directory
    VolumeMount(source=str(current_dir), target="/workspace"),
    # Persist apt cache
    VolumeMount(source="apt-cache", target="/var/cache/apt"),
    # Persist home directory
    VolumeMount(source="ubuntu-home", target="/root"),
  ],
  # Common development ports
  ports={
    22: {"HostPort": 2222},  # SSH
    8080: {"HostPort": 8080},  # Web development
    3000: {"HostPort": 3000},  # Node.js apps
    5000: {"HostPort": 5000},  # Python Flask/FastAPI
  },
  environment={"DEBIAN_FRONTEND": "noninteractive", "TZ": "UTC", "LANG": "C.UTF-8"},
  # SSH configuration
  ssh=SSHConfig(port=22),
  # Resource limits
  memory="4g",
  cpus=4.0,
)

# Note: To initialize the environment with development tools, SSH in and run:
# apt-get update && apt-get install -y build-essential git curl wget vim nano
# apt-get install -y htop tree jq unzip zip sudo
# apt-get install -y net-tools iputils-ping dnsutils netcat
# apt-get install -y python3 python3-pip nodejs npm
# apt-get install -y tmux screen ripgrep fd-find bat
