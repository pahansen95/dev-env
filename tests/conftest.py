"""Test configuration and fixtures for dev-env"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from dev_env.config import Environment, VolumeMount, GitConfig, NetworkConfig
from dev_env.state import StateManager
from dev_env.docker import DockerClient


@pytest.fixture
def temp_dir():
  """Create a temporary directory for test files"""
  with tempfile.TemporaryDirectory() as tmp_dir:
    yield Path(tmp_dir)


@pytest.fixture
def state_manager(temp_dir):
  """Create a StateManager with temporary database"""
  return StateManager(temp_dir / "state")


@pytest.fixture
def mock_docker():
  """Mock Docker client for testing without Docker dependency"""
  with patch("dev_env.docker.DockerClient") as mock_client:
    mock_instance = Mock(spec=DockerClient)
    mock_client.return_value = mock_instance

    # Configure common return values
    mock_instance.pull_image.return_value = None
    mock_instance.create_container.return_value = "container_123"
    mock_instance.start_container.return_value = None
    mock_instance.get_container.return_value = {
      "State": {"Status": "running"},
      "Config": {"Image": "python:3.13"},
      "NetworkSettings": {"Ports": {}},
    }
    mock_instance.wait_for_container_ready.return_value = True

    yield mock_instance


@pytest.fixture
def sample_environment():
  """Create a sample Environment configuration for testing"""
  return Environment(
    name="test-env",
    base_image="python:3.13",
    command=["sleep", "infinity"],
    ports={22: 2222, 8000: 8000},
    environment={"TEST_VAR": "test_value"},
    volumes=[VolumeMount(source="test-vol", target="/data"), VolumeMount(source="/tmp", target="/tmp")],
    network=NetworkConfig(name="test-network", driver="bridge"),
    git=GitConfig(url="https://github.com/test/repo.git", path="/workspace"),
  )


@pytest.fixture
def sample_config_file(temp_dir, sample_environment):
  """Create a sample configuration file"""
  config_file = temp_dir / "test_config.py"
  config_content = f'''
from dev_env.config import Environment, VolumeMount, GitConfig, NetworkConfig

config = Environment(
    name="{sample_environment.name}",
    base_image="{sample_environment.base_image}",
    command={sample_environment.command!r},
    ports={sample_environment.ports!r},
    environment={sample_environment.environment!r},
    volumes=[
        VolumeMount(source="test-vol", target="/data"),
        VolumeMount(source="/tmp", target="/tmp")
    ],
    network=NetworkConfig(name="test-network", driver="bridge"),
    git=GitConfig(url="https://github.com/test/repo.git", path="/workspace")
)
'''
  config_file.write_text(config_content)
  return config_file


@pytest.fixture
def mock_check_docker_available():
  """Mock Docker availability check"""
  with patch("dev_env.utils.check_docker_available", return_value=True):
    yield


@pytest.fixture
def mock_docker_unavailable():
  """Mock Docker as unavailable"""
  with patch("dev_env.utils.check_docker_available", return_value=False):
    yield


@pytest.fixture
def mock_ssh_utils():
  """Mock SSH-related utilities"""
  with (
    patch("dev_env.utils.setup_ssh_server") as mock_setup,
    patch("dev_env.utils.inject_ssh_key") as mock_inject,
    patch("dev_env.utils.get_host_ssh_key", return_value="ssh-rsa AAAA...") as mock_key,
  ):
    yield {"setup_ssh_server": mock_setup, "inject_ssh_key": mock_inject, "get_host_ssh_key": mock_key}


@pytest.fixture
def mock_git_utils():
  """Mock Git-related utilities"""
  with (
    patch("dev_env.utils.setup_git_in_container") as mock_setup,
    patch(
      "dev_env.utils.get_host_git_config", return_value={"user.name": "Test", "user.email": "test@example.com"}
    ) as mock_config,
  ):
    yield {"setup_git_in_container": mock_setup, "get_host_git_config": mock_config}


@pytest.fixture
def captured_output():
  """Capture stdout/stderr for testing CLI output"""
  with patch("sys.stdout") as mock_stdout, patch("sys.stderr") as mock_stderr:
    yield {"stdout": mock_stdout, "stderr": mock_stderr}


@pytest.fixture
def mock_subprocess():
  """Mock subprocess calls"""
  with patch("subprocess.call", return_value=0) as mock_call, patch("subprocess.run") as mock_run:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = ""
    yield {"call": mock_call, "run": mock_run}


@pytest.fixture(autouse=True)
def clean_environment():
  """Clean up environment variables between tests"""
  import os

  original_env = os.environ.copy()
  yield
  # Restore original environment
  os.environ.clear()
  os.environ.update(original_env)
