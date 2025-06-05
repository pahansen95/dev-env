"""Tests for configuration detection."""

from dev_env.config_detector import ConfigDetector


class TestConfigDetector:
  """Test configuration detection functionality."""

  def test_detect_dev_env_yaml(self, tmp_path):
    """Test detection of existing dev-env.yaml."""
    config_path = tmp_path / "dev-env.yaml"
    config_path.write_text("name: test\nimage: ubuntu:22.04")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "dev-env"
    assert result["path"] == str(config_path)

  def test_detect_devcontainer(self, tmp_path):
    """Test detection of devcontainer.json."""
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    devcontainer_path = devcontainer_dir / "devcontainer.json"
    devcontainer_path.write_text("""
    {
      "image": "mcr.microsoft.com/devcontainers/python:3.11",
      "remoteUser": "vscode",
      "features": {
        "ghcr.io/devcontainers/features/git:1": {}
      }
    }
    """)

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "devcontainer"
    assert result["path"] == str(devcontainer_path)
    assert result["image"] == "mcr.microsoft.com/devcontainers/python:3.11"
    assert result["remoteUser"] == "vscode"
    assert "features" in result

  def test_detect_dockerfile(self, tmp_path):
    """Test detection of Dockerfile."""
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("""
    FROM python:3.11-slim
    WORKDIR /app
    COPY . .
    RUN pip install -r requirements.txt
    """)

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "dockerfile"
    assert result["path"] == str(dockerfile)
    assert result["base_image"] == "python:3.11-slim"

  def test_detect_docker_compose(self, tmp_path):
    """Test detection of docker-compose.yaml."""
    compose_path = tmp_path / "docker-compose.yaml"
    compose_path.write_text("version: '3'\nservices:\n  app:\n    image: node:18")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "docker-compose"
    assert result["path"] == str(compose_path)

  def test_detect_python_project(self, tmp_path):
    """Test detection of Python project."""
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("flask==2.0.0\nrequests==2.28.0")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "python"
    assert result["files"]["requirements"] is True
    assert result["suggested_image"] == "python:3.11-slim"

  def test_detect_nodejs_project(self, tmp_path):
    """Test detection of Node.js project."""
    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "test-app", "version": "1.0.0"}')

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "nodejs"
    assert result["files"]["package_json"] is True
    assert result["suggested_image"] == "node:18-slim"

  def test_detect_go_project(self, tmp_path):
    """Test detection of Go project."""
    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module example.com/test\n\ngo 1.21")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "go"
    assert result["files"]["go_mod"] is True
    assert result["suggested_image"] == "golang:1.21-alpine"

  def test_detect_rust_project(self, tmp_path):
    """Test detection of Rust project."""
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text('[package]\nname = "test"\nversion = "0.1.0"')

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "rust"
    assert result["files"]["cargo_toml"] is True
    assert result["suggested_image"] == "rust:slim"

  def test_detect_ruby_project(self, tmp_path):
    """Test detection of Ruby project."""
    gemfile = tmp_path / "Gemfile"
    gemfile.write_text('source "https://rubygems.org"\ngem "rails"')

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "ruby"
    assert result["files"]["gemfile"] is True
    assert result["suggested_image"] == "ruby:3-slim"

  def test_detect_java_maven_project(self, tmp_path):
    """Test detection of Java Maven project."""
    pom_xml = tmp_path / "pom.xml"
    pom_xml.write_text("<project><modelVersion>4.0.0</modelVersion></project>")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "java"
    assert result["build_tool"] == "maven"
    assert result["files"]["pom_xml"] is True
    assert result["suggested_image"] == "maven:3-openjdk-17-slim"

  def test_detect_java_gradle_project(self, tmp_path):
    """Test detection of Java Gradle project."""
    build_gradle = tmp_path / "build.gradle"
    build_gradle.write_text("plugins { id 'java' }")

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is not None
    assert result["type"] == "language"
    assert result["language"] == "java"
    assert result["build_tool"] == "gradle"
    assert result["files"]["build_gradle"] is True
    assert result["suggested_image"] == "gradle:7-jdk17-alpine"

  def test_detect_nothing(self, tmp_path):
    """Test when no configuration is detected."""
    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    assert result is None

  def test_detection_priority(self, tmp_path):
    """Test that dev-env.yaml takes priority over other configs."""
    # Create both dev-env.yaml and package.json
    config_path = tmp_path / "dev-env.yaml"
    config_path.write_text("name: test")

    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "test"}')

    detector = ConfigDetector()
    result = detector.detect(tmp_path)

    # dev-env.yaml should be detected first
    assert result["type"] == "dev-env"
