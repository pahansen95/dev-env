#!/usr/bin/env python3
"""
General Purpose Ubuntu Development Environment

This example provides a flexible Ubuntu environment for:
- General development and experimentation
- System administration tasks
- Multi-language development
- Tool installation and testing

Usage:
  # Basic Ubuntu environment
  dev-env run examples/ubuntu.py

  # With additional ports
  dev-env run examples/ubuntu.py -p 8080:8080 -p 5432:5432
"""

from pathlib import Path
from dev_env.config import Environment, VolumeMount

# Get current directory
current_dir = Path.cwd()

# General purpose Ubuntu environment
environment = Environment(
  name="ubuntu-dev",
  base_image="ubuntu:22.04",
  volumes=[
    # Mount current directory
    VolumeMount(source=str(current_dir), target="/workspace", mode="rw"),
    # Share Docker socket for Docker-in-Docker scenarios
    VolumeMount(source="/var/run/docker.sock", target="/var/run/docker.sock", mode="rw"),
    # Persist apt cache
    VolumeMount(source="apt-cache", target="/var/cache/apt", mode="rw"),
    # Persist home directory
    VolumeMount(source="ubuntu-home", target="/root", mode="rw"),
  ],
  working_dir="/workspace",
  command=["/bin/bash"],
  # Common development ports
  ports=["8080:8080", "3000:3000", "5000:5000"],
  environment={"DEBIAN_FRONTEND": "noninteractive", "TZ": "UTC", "LANG": "C.UTF-8"},
  init_commands=[
    # Update package lists
    "apt-get update",
    # Install essential development tools
    "apt-get install -y build-essential git curl wget vim nano",
    # Install common utilities
    "apt-get install -y htop tree jq unzip zip sudo",
    # Install network tools
    "apt-get install -y net-tools iputils-ping dnsutils netcat",
    # Install Python and Node.js
    "apt-get install -y python3 python3-pip nodejs npm",
    # Install Docker CLI for Docker-in-Docker
    "curl -fsSL https://get.docker.com | sh",
    # Install useful development tools
    "apt-get install -y tmux screen ripgrep fd-find bat",
    # Set up locale
    "apt-get install -y locales && locale-gen en_US.UTF-8",
    # Create useful aliases
    "echo 'alias ll=\"ls -alF\"' >> /root/.bashrc",
    "echo 'alias la=\"ls -A\"' >> /root/.bashrc",
    "echo 'alias l=\"ls -CF\"' >> /root/.bashrc",
    # Display system info
    "echo '=== Ubuntu Development Environment ===' && uname -a && echo",
    "echo 'Available tools: git, python3, node, docker, vim, tmux, and more'",
  ],
)
