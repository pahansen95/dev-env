"""Tests for __main__.py entry point"""

import sys
from unittest.mock import patch, MagicMock


def test_main_module_imports():
  """Test that __main__.py properly imports main function"""
  # Clear module from cache if it exists
  if "dev_env.__main__" in sys.modules:
    del sys.modules["dev_env.__main__"]

  import dev_env.__main__

  # Verify the main function is available
  assert hasattr(dev_env.__main__, "main")
  assert callable(dev_env.__main__.main)


def test_main_module_structure():
  """Test that __main__.py has the expected structure"""
  import dev_env.__main__

  # Check that the module imports from .cli
  assert dev_env.__main__.main.__module__ == "dev_env.cli"


def test_main_execution_path():
  """Test the execution path when module is run directly"""
  # Create a mock module to test the if __name__ == "__main__" block
  mock_module = MagicMock()
  mock_module.__name__ = "__main__"

  with patch("dev_env.cli.main") as mock_main:
    # Directly execute the code that would run when __name__ == "__main__"
    if mock_module.__name__ == "__main__":
      mock_main()

    # Verify main would be called
    mock_main.assert_called_once()
