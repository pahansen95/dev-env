"""File system operations and management tools"""

import logging
import shutil

from ..server import mcp
from ..core import get_safe_path, find_git_root

logger = logging.getLogger(__name__)


@mcp.tool()
def read_file(path: str) -> str:
  """Read a file from the project

  Args:
      path: File path relative to project root

  Returns:
      File contents as string

  Raises:
      FileNotFoundError: File doesn't exist
      IsADirectoryError: Path points to directory
      PermissionError: No read permission
  """
  logger.info(f"read_file called with path='{path}'")

  try:
    file_path = get_safe_path(path, must_exist=True)

    # Verify it's a file, not a directory
    if file_path.is_dir():
      raise IsADirectoryError(f"Path '{path}' is a directory, not a file")

    content = file_path.read_text(encoding="utf-8")
    logger.info(f"Successfully read {len(content)} characters from {path}")
    return content
  except UnicodeDecodeError:
    # Try reading as binary and determine encoding
    logger.warning(f"Failed to read {path} as UTF-8, attempting binary read")
    raise ValueError(f"File '{path}' is not a valid UTF-8 text file")


@mcp.tool()
def write_file(path: str, content: str) -> str:
  """Write content to a file in the project

  Args:
      path: File path relative to project root
      content: Content to write

  Returns:
      Success message

  Raises:
      IsADirectoryError: Path points to existing directory
      PermissionError: No write permission
  """
  logger.info(f"write_file called with path='{path}'")

  try:
    file_path = get_safe_path(path)

    # Check if path exists and is a directory
    if file_path.exists() and file_path.is_dir():
      raise IsADirectoryError(f"Path '{path}' is a directory, cannot write file")

    # Create parent directories if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write content
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Successfully wrote {len(content)} characters to {path}")
    return f"Successfully wrote to {path}"
  except Exception as e:
    logger.error(f"Failed to write file {path}: {e}")
    raise


@mcp.tool()
def create_directory(path: str) -> str:
  """Create a directory in the project

  Args:
      path: Directory path relative to project root

  Returns:
      Success message

  Raises:
      FileExistsError: Path exists as a file
      PermissionError: No write permission
  """
  logger.info(f"create_directory called with path='{path}'")

  try:
    dir_path = get_safe_path(path)

    # Check if path exists as a file
    if dir_path.exists() and dir_path.is_file():
      raise FileExistsError(f"Path '{path}' already exists as a file")

    dir_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Successfully created directory: {path}")
    return f"Successfully created directory: {path}"
  except Exception as e:
    logger.error(f"Failed to create directory {path}: {e}")
    raise


@mcp.tool()
def move_file(source: str, destination: str) -> dict:
  """Move or rename a file or directory

  Args:
      source: Source path relative to project root
      destination: Destination path relative to project root

  Returns:
      Dict with status and paths
  """
  logger.info(f"move_file called: {source} -> {destination}")

  try:
    source_path = get_safe_path(source, must_exist=True)
    dest_path = get_safe_path(destination)

    # Check if source and destination are the same
    if source_path.resolve() == dest_path.resolve():
      return {"status": "error", "error": "Source and destination are the same"}

    # Check if destination exists
    if dest_path.exists():
      if dest_path.is_dir() and source_path.is_file():
        # Moving file into existing directory
        dest_path = dest_path / source_path.name
      elif dest_path.is_file():
        return {"status": "error", "error": f"Destination file '{destination}' already exists"}

    # Create destination directory if needed
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the file/directory
    shutil.move(str(source_path), str(dest_path))

    return {
      "status": "success",
      "source": str(source_path.relative_to(find_git_root())),
      "destination": str(dest_path.relative_to(find_git_root())),
    }
  except FileNotFoundError as e:
    logger.error(f"Source file not found: {e}")
    return {"status": "error", "error": f"Source file '{source}' not found"}
  except PermissionError as e:
    logger.error(f"Permission denied: {e}")
    return {"status": "error", "error": "Permission denied"}
  except Exception as e:
    logger.error(f"Failed to move: {e}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def delete_file(path: str) -> dict:
  """Delete a file or directory

  Args:
      path: Path to delete relative to project root

  Returns:
      Dict with status and deleted path
  """
  logger.info(f"delete_file called for {path}")

  try:
    target_path = get_safe_path(path, must_exist=True)

    # Safety check - don't delete project root or critical directories
    git_root = find_git_root()
    critical_dirs = {git_root, git_root / ".git", git_root / ".venv"}

    if target_path in critical_dirs:
      return {"status": "error", "error": f"Cannot delete critical directory: {path}"}

    # Delete based on type
    if target_path.is_dir():
      # Check if directory is empty
      if any(target_path.iterdir()):
        # Non-empty directory, use rmtree
        shutil.rmtree(target_path)
        logger.info(f"Deleted directory tree: {path}")
      else:
        # Empty directory
        target_path.rmdir()
        logger.info(f"Deleted empty directory: {path}")
    else:
      target_path.unlink()
      logger.info(f"Deleted file: {path}")

    return {"status": "success", "deleted": str(target_path.relative_to(git_root))}
  except FileNotFoundError:
    return {"status": "error", "error": f"Path '{path}' not found"}
  except PermissionError:
    return {"status": "error", "error": "Permission denied"}
  except Exception as e:
    logger.error(f"Failed to delete: {e}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def copy_file(source: str, destination: str) -> dict:
  """Copy a file or directory

  Args:
      source: Source path relative to project root
      destination: Destination path relative to project root

  Returns:
      Dict with status and paths
  """
  logger.info(f"copy_file called: {source} -> {destination}")

  try:
    source_path = get_safe_path(source, must_exist=True)
    dest_path = get_safe_path(destination)

    # Check if source and destination are the same
    if source_path.resolve() == dest_path.resolve():
      return {"status": "error", "error": "Cannot copy file to itself"}

    # Handle copying into directories
    if dest_path.exists() and dest_path.is_dir():
      # Copy into the directory with same name
      dest_path = dest_path / source_path.name

    # Check if destination already exists
    if dest_path.exists():
      return {"status": "error", "error": f"Destination '{destination}' already exists"}

    # Copy based on type
    if source_path.is_dir():
      shutil.copytree(source_path, dest_path, dirs_exist_ok=False)
      logger.info(f"Copied directory tree: {source} -> {destination}")
    else:
      dest_path.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(source_path, dest_path)
      logger.info(f"Copied file: {source} -> {destination}")

    return {
      "status": "success",
      "source": str(source_path.relative_to(find_git_root())),
      "destination": str(dest_path.relative_to(find_git_root())),
    }
  except FileNotFoundError:
    return {"status": "error", "error": f"Source path '{source}' not found"}
  except PermissionError:
    return {"status": "error", "error": "Permission denied"}
  except Exception as e:
    logger.error(f"Failed to copy: {e}")
    return {"status": "error", "error": str(e)}
