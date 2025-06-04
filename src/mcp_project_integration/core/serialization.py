"""Python configuration file serialization

# Configuration as Code Mental Model

This module implements a fundamental design principle: configuration should be
executable Python code rather than static data formats. This approach provides
several key advantages:

## Type Safety and Native Support

Unlike JSON/YAML/TOML, Python configurations support:
- Native datetime objects without string conversion
- Enum types with proper validation
- Path objects for filesystem operations
- Complex type hierarchies and inheritance

## Human Readability and Debugging

Python configuration files are:
- Directly executable for testing (`python config.py`)
- Syntax-highlighted in all Python-aware editors
- Debuggable with standard Python tools
- Self-documenting through Python's type system

## Version Control Benefits

Python files provide:
- Clear diff visibility for configuration changes
- Ability to add comments and documentation
- Conditional logic when needed (though discouraged)
- Import capabilities for shared configuration

## Implementation Philosophy

The serializer maintains a balance between flexibility and safety:
- Supports common Python types automatically
- Preserves type information during round-trips
- Generates clean, readable output
- Handles nested structures gracefully

This approach transforms configuration from passive data into active,
verifiable code that participates in the development workflow.
"""

import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PythonConfigSerializer:
  """Manages serialization of configuration data to Python files

  This serializer converts dictionaries into executable Python files that can
  be imported dynamically. Supports datetime objects, enums, and nested structures.
  """

  @staticmethod
  def serialize_value(value: Any) -> str:
    """Convert Python value to string representation

    Handles special types:
    - datetime: Serialized as datetime.fromisoformat() calls
    - Enum: Serialized as EnumClass.MEMBER references
    - Path: Serialized as Path() constructors
    """
    if isinstance(value, datetime):
      return f'datetime.fromisoformat("{value.isoformat()}")'
    elif isinstance(value, Enum):
      return f"{value.__class__.__name__}.{value.name}"
    elif isinstance(value, Path):
      return f'Path("{value}")'
    elif isinstance(value, str):
      return repr(value)
    elif isinstance(value, (list, dict, tuple)):
      return repr(value)
    else:
      return str(value)

  @classmethod
  def write_config(
    cls,
    path: Path,
    config_name: str,
    data: Dict[str, Any],
    imports: Optional[Dict[str, str]] = None,
    header: Optional[str] = None,
  ) -> None:
    """Write configuration dictionary to Python file

    Args:
        path: Target file path
        config_name: Variable name for configuration (e.g., "SESSION_CONFIG")
        data: Configuration data to serialize
        imports: Dict mapping module names to import statements
        header: Optional comment header for the file
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
      # Write header
      if header:
        f.write(f"# {header}\n")
      else:
        f.write("# Auto-generated configuration file\n")

      # Write imports
      if imports:
        for import_stmt in imports.values():
          f.write(f"{import_stmt}\n")
      else:
        # Default imports
        f.write("from datetime import datetime\n")
        f.write("from pathlib import Path\n")
      f.write("\n")

      # Write configuration
      f.write(f"{config_name} = {{\n")

      # Serialize each field
      for key, value in data.items():
        serialized = cls.serialize_value(value)
        f.write(f'    "{key}": {serialized},\n')

      f.write("}\n")

    logger.debug(f"Wrote configuration to {path}")

  @classmethod
  def read_config(cls, path: Path, config_name: str) -> Dict[str, Any]:
    """Read configuration from Python file

    Args:
        path: Path to Python configuration file
        config_name: Variable name containing configuration

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: Configuration file doesn't exist
        AttributeError: Configuration variable not found
    """
    if not path.exists():
      raise FileNotFoundError(f"Configuration file not found: {path}")

    # Load module dynamically
    spec = importlib.util.spec_from_file_location("config", path)
    if not spec or not spec.loader:
      raise ImportError(f"Failed to load module spec from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Extract configuration
    if not hasattr(module, config_name):
      raise AttributeError(f"Configuration '{config_name}' not found in {path}")

    config = getattr(module, config_name)
    logger.debug(f"Read configuration from {path}")

    return config

  @classmethod
  def update_config(
    cls, path: Path, config_name: str, updates: Dict[str, Any], create_if_missing: bool = False
  ) -> Dict[str, Any]:
    """Update existing configuration file

    Reads current configuration, applies updates, and rewrites file.

    Args:
        path: Path to configuration file
        config_name: Variable name for configuration
        updates: Dictionary of updates to apply
        create_if_missing: Create file if it doesn't exist

    Returns:
        Updated configuration dictionary
    """
    # Read existing or start fresh
    if path.exists():
      current = cls.read_config(path, config_name)
    elif create_if_missing:
      current = {}
    else:
      raise FileNotFoundError(f"Configuration file not found: {path}")

    # Apply updates
    current.update(updates)

    # Rewrite file
    cls.write_config(path, config_name, current)

    return current
