"""File system operations and management tools"""

import logging
import shutil

from ..server import mcp
from ..utils import get_safe_path, find_git_root

logger = logging.getLogger(__name__)


@mcp.tool()
def read_file(path: str) -> str:
  """Read a file from the project"""
  logger.info(f"read_file called with path='{path}'")
  file_path = get_safe_path(path, must_exist=True)
  content = file_path.read_text(encoding="utf-8")
  logger.info(f"Successfully read {len(content)} characters from {path}")
  return content


@mcp.tool()
def write_file(path: str, content: str) -> str:
  """Write content to a file in the project"""
  logger.info(f"write_file called with path='{path}'")
  file_path = get_safe_path(path)
  file_path.parent.mkdir(parents=True, exist_ok=True)
  file_path.write_text(content, encoding="utf-8")
  logger.info(f"Successfully wrote {len(content)} characters to {path}")
  return f"Successfully wrote to {path}"


@mcp.tool()
def create_directory(path: str) -> str:
  """Create a directory in the project"""
  logger.info(f"create_directory called with path='{path}'")
  dir_path = get_safe_path(path)
  dir_path.mkdir(parents=True, exist_ok=True)
  logger.info(f"Successfully created directory: {path}")
  return f"Successfully created directory: {path}"


@mcp.tool()
def move_file(source: str, destination: str) -> dict:
  """Move or rename a file or directory"""
  logger.info(f"move_file called: {source} -> {destination}")

  try:
    source_path = get_safe_path(source, must_exist=True)
    dest_path = get_safe_path(destination)

    # Create destination directory if needed
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the file/directory
    shutil.move(str(source_path), str(dest_path))

    return {
      "status": "success",
      "source": str(source_path.relative_to(find_git_root())),
      "destination": str(dest_path.relative_to(find_git_root())),
    }
  except Exception as e:
    logger.error(f"Failed to move: {e}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def delete_file(path: str) -> dict:
  """Delete a file or directory"""
  logger.info(f"delete_file called for {path}")

  try:
    target_path = get_safe_path(path, must_exist=True)

    if target_path.is_dir():
      shutil.rmtree(target_path)
    else:
      target_path.unlink()

    return {"status": "success", "deleted": str(target_path.relative_to(find_git_root()))}
  except Exception as e:
    logger.error(f"Failed to delete: {e}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def copy_file(source: str, destination: str) -> dict:
  """Copy a file or directory"""
  logger.info(f"copy_file called: {source} -> {destination}")

  try:
    source_path = get_safe_path(source, must_exist=True)
    dest_path = get_safe_path(destination)

    if source_path.is_dir():
      shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
    else:
      dest_path.parent.mkdir(parents=True, exist_ok=True)
      shutil.copy2(source_path, dest_path)

    return {
      "status": "success",
      "source": str(source_path.relative_to(find_git_root())),
      "destination": str(dest_path.relative_to(find_git_root())),
    }
  except Exception as e:
    logger.error(f"Failed to copy: {e}")
    return {"status": "error", "error": str(e)}
