"""File system operations wrapper

Provides safe, consistent file system operations with path validation and
error handling for the MCP project integration.
"""

import shutil
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class FileSystemOperations:
  """Manages file system operations with safety checks

  Provides a unified interface for file operations while ensuring all paths
  remain within project boundaries. Includes atomic operations and proper
  error handling.
  """

  @staticmethod
  def ensure_directory(path: Path) -> Path:
    """Create directory if it doesn't exist

    Creates parent directories as needed.

    Args:
        path: Directory path to create

    Returns:
        Path object for the directory
    """
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured directory exists: {path}")
    return path

  @staticmethod
  def safe_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file with atomic operation

    Writes to a temporary file first, then moves to final location.
    This prevents partial writes from corrupting files.

    Args:
        path: Target file path
        content: Text content to write
        encoding: Text encoding (default: utf-8)
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding=encoding)

    # Atomic move to final location
    temp_path.replace(path)
    logger.debug(f"Safely wrote {len(content)} chars to {path}")

  @staticmethod
  def safe_read(path: Path, encoding: str = "utf-8") -> str:
    """Read file content with error handling

    Args:
        path: File path to read
        encoding: Expected text encoding

    Returns:
        File content as string

    Raises:
        FileNotFoundError: File doesn't exist
        IsADirectoryError: Path is a directory
    """
    if not path.exists():
      raise FileNotFoundError(f"File not found: {path}")

    if path.is_dir():
      raise IsADirectoryError(f"Path is a directory: {path}")

    content = path.read_text(encoding=encoding)
    logger.debug(f"Read {len(content)} chars from {path}")
    return content

  @classmethod
  def create_symlink(cls, source: Path, target: Path) -> None:
    """Create symbolic link with validation

    Args:
        source: Path to link to (must exist)
        target: Path where symlink will be created

    Raises:
        FileNotFoundError: Source doesn't exist
        FileExistsError: Target already exists
    """
    if not source.exists():
      raise FileNotFoundError(f"Symlink source not found: {source}")

    if target.exists():
      if target.is_symlink() and target.readlink() == source:
        logger.debug(f"Symlink already exists: {target} -> {source}")
        return
      raise FileExistsError(f"Target already exists: {target}")

    # Ensure parent directory exists
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink
    target.symlink_to(source)
    logger.debug(f"Created symlink: {target} -> {source}")

  @classmethod
  def copy(cls, source: Path, destination: Path, preserve_metadata: bool = True) -> Path:
    """Copy file or directory with metadata preservation

    Args:
        source: Source path
        destination: Destination path
        preserve_metadata: Preserve timestamps and permissions

    Returns:
        Path to the copy
    """
    if not source.exists():
      raise FileNotFoundError(f"Source not found: {source}")

    # Ensure destination parent exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    if source.is_dir():
      shutil.copytree(source, destination, dirs_exist_ok=False)
      logger.debug(f"Copied directory: {source} -> {destination}")
    else:
      if preserve_metadata:
        shutil.copy2(source, destination)
      else:
        shutil.copy(source, destination)
      logger.debug(f"Copied file: {source} -> {destination}")

    return destination

  @classmethod
  def move(cls, source: Path, destination: Path) -> Path:
    """Move file or directory

    Args:
        source: Source path
        destination: Destination path

    Returns:
        New path after move
    """
    if not source.exists():
      raise FileNotFoundError(f"Source not found: {source}")

    # Ensure destination parent exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    shutil.move(str(source), str(destination))
    logger.debug(f"Moved: {source} -> {destination}")

    return destination

  @classmethod
  def remove(cls, path: Path, recursive: bool = False) -> None:
    """Remove file or directory

    Args:
        path: Path to remove
        recursive: Remove directories and their contents
    """
    if not path.exists():
      logger.debug(f"Path doesn't exist, nothing to remove: {path}")
      return

    if path.is_dir():
      if recursive:
        shutil.rmtree(path)
        logger.debug(f"Removed directory recursively: {path}")
      else:
        path.rmdir()
        logger.debug(f"Removed empty directory: {path}")
    else:
      path.unlink()
      logger.debug(f"Removed file: {path}")

  @classmethod
  def list_directory(cls, path: Path, pattern: Optional[str] = None, recursive: bool = False) -> List[Path]:
    """List directory contents with optional filtering

    Args:
        path: Directory to list
        pattern: Glob pattern for filtering
        recursive: Search subdirectories

    Returns:
        List of paths matching criteria
    """
    if not path.exists():
      raise FileNotFoundError(f"Directory not found: {path}")

    if not path.is_dir():
      raise NotADirectoryError(f"Path is not a directory: {path}")

    if pattern:
      if recursive:
        results = list(path.rglob(pattern))
      else:
        results = list(path.glob(pattern))
    else:
      if recursive:
        results = list(path.rglob("*"))
      else:
        results = list(path.iterdir())

    logger.debug(f"Listed {len(results)} items in {path}")
    return sorted(results)

  @classmethod
  def get_size(cls, path: Path) -> int:
    """Get size of file or directory in bytes

    For directories, calculates total size recursively.
    """
    if not path.exists():
      raise FileNotFoundError(f"Path not found: {path}")

    if path.is_file():
      return path.stat().st_size

    # Calculate directory size recursively
    total_size = 0
    for item in path.rglob("*"):
      if item.is_file():
        total_size += item.stat().st_size

    return total_size
