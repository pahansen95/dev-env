"""Configuration detection for development environments."""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigDetector:
  """Detect and analyze project configurations."""

  def detect(self, path: Path) -> Optional[Dict[str, Any]]:
    """
    Detect configuration from various sources.

    Detection order:
    1. .devcontainer/devcontainer.json
    2. dev-env.yaml
    3. docker-compose.yaml
    4. Dockerfile
    5. Language-specific files (package.json, requirements.txt)
    """
    # Check for existing dev-env.yaml
    if (path / "dev-env.yaml").exists():
      return {"type": "dev-env", "path": str(path / "dev-env.yaml")}

    # Check for devcontainer
    devcontainer_path = path / ".devcontainer" / "devcontainer.json"
    if devcontainer_path.exists():
      return self._detect_devcontainer(devcontainer_path)

    # Check for docker-compose
    for compose_file in ["docker-compose.yaml", "docker-compose.yml", "compose.yaml", "compose.yml"]:
      compose_path = path / compose_file
      if compose_path.exists():
        return self._detect_docker_compose(compose_path)

    # Check for Dockerfile
    dockerfile_path = path / "Dockerfile"
    if dockerfile_path.exists():
      return self._detect_dockerfile(dockerfile_path)

    # Check for language-specific files
    lang_config = self._detect_language(path)
    if lang_config:
      return lang_config

    return None

  def _detect_devcontainer(self, path: Path) -> Dict[str, Any]:
    """Detect configuration from devcontainer.json."""
    try:
      with open(path) as f:
        config = json.load(f)

      return {
        "type": "devcontainer",
        "path": str(path),
        "image": config.get("image"),
        "dockerfile": config.get("dockerFile"),
        "features": config.get("features", {}),
        "customizations": config.get("customizations", {}),
        "postCreateCommand": config.get("postCreateCommand"),
        "remoteUser": config.get("remoteUser", "vscode"),
      }
    except Exception:
      return {"type": "devcontainer", "path": str(path), "error": "Failed to parse"}

  def _detect_docker_compose(self, path: Path) -> Dict[str, Any]:
    """Detect configuration from docker-compose.yaml."""
    # For now, just note that it exists
    # Full parsing would require a YAML parser
    return {
      "type": "docker-compose",
      "path": str(path),
      "services": [],  # Would parse services here
    }

  def _detect_dockerfile(self, path: Path) -> Dict[str, Any]:
    """Detect configuration from Dockerfile."""
    try:
      with open(path) as f:
        content = f.read()

      # Extract base image
      base_image = None
      for line in content.splitlines():
        if line.strip().upper().startswith("FROM "):
          base_image = line.split(None, 1)[1].strip()
          break

      return {
        "type": "dockerfile",
        "path": str(path),
        "base_image": base_image,
      }
    except Exception:
      return {"type": "dockerfile", "path": str(path), "error": "Failed to parse"}

  def _detect_language(self, path: Path) -> Optional[Dict[str, Any]]:
    """Detect language-specific configuration files."""
    # Python
    if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
      return {
        "type": "language",
        "language": "python",
        "files": {
          "requirements": (path / "requirements.txt").exists(),
          "pyproject": (path / "pyproject.toml").exists(),
          "setup_py": (path / "setup.py").exists(),
        },
        "suggested_image": "python:3.11-slim",
      }

    # Node.js
    if (path / "package.json").exists():
      return {
        "type": "language",
        "language": "nodejs",
        "files": {
          "package_json": True,
          "package_lock": (path / "package-lock.json").exists(),
          "yarn_lock": (path / "yarn.lock").exists(),
        },
        "suggested_image": "node:18-slim",
      }

    # Go
    if (path / "go.mod").exists():
      return {
        "type": "language",
        "language": "go",
        "files": {
          "go_mod": True,
          "go_sum": (path / "go.sum").exists(),
        },
        "suggested_image": "golang:1.21-alpine",
      }

    # Rust
    if (path / "Cargo.toml").exists():
      return {
        "type": "language",
        "language": "rust",
        "files": {
          "cargo_toml": True,
          "cargo_lock": (path / "Cargo.lock").exists(),
        },
        "suggested_image": "rust:slim",
      }

    # Ruby
    if (path / "Gemfile").exists():
      return {
        "type": "language",
        "language": "ruby",
        "files": {
          "gemfile": True,
          "gemfile_lock": (path / "Gemfile.lock").exists(),
        },
        "suggested_image": "ruby:3-slim",
      }

    # Java/Maven
    if (path / "pom.xml").exists():
      return {
        "type": "language",
        "language": "java",
        "build_tool": "maven",
        "files": {"pom_xml": True},
        "suggested_image": "maven:3-openjdk-17-slim",
      }

    # Java/Gradle
    if (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
      return {
        "type": "language",
        "language": "java",
        "build_tool": "gradle",
        "files": {
          "build_gradle": (path / "build.gradle").exists(),
          "build_gradle_kts": (path / "build.gradle.kts").exists(),
        },
        "suggested_image": "gradle:7-jdk17-alpine",
      }

    return None
