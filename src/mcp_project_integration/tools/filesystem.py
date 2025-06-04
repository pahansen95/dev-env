"""File system operations and management tools"""

import logging
import shutil

from ..server import mcp
from ..core import get_safe_path, find_git_root

logger = logging.getLogger(__name__)


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True})
def read_file(path: str) -> str:
  """Read a file from the project

  Args:
      path: File path relative to project root

  Returns:
      File contents as string

  Use when:
  - Examining source code files
  - Reading configuration files
  - Analyzing documentation
  - Verifying file contents before modification

  Not suitable for:
  - Binary files (will raise ValueError)
  - Files outside project root (security boundary)
  - Very large files (may consume excessive memory)

  Common errors:
  - FileNotFoundError: Path doesn't exist
    → Verify path with find() tool first
  - IsADirectoryError: Path is a directory
    → Use find() to list directory contents
  - ValueError: File is not valid UTF-8
    → File may be binary or use different encoding
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


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # Creates/overwrites but doesn't delete
    "idempotentHint": False,  # Overwrites existing content
    "openWorldHint": False,
  }
)
def write_file(path: str, content: str) -> str:
  """Write content to a file in the project

  Args:
      path: File path relative to project root
      content: Content to write

  Returns:
      Success message

  Use when:
  - Creating new source files
  - Updating configuration
  - Generating documentation
  - Applying code modifications

  Side effects:
  - Creates parent directories if needed
  - Overwrites existing file content without warning
  - File timestamp updated
  - May trigger file watchers or build systems

  Security constraints:
  - Path must be within project root
  - Cannot write to .git directory
  - Cannot overwrite critical system files

  Common errors:
  - IsADirectoryError: Path exists as directory
    → Choose different filename or delete directory first
  - PermissionError: Insufficient write permissions
    → Check file permissions or ownership

  Example: write_file("src/config.py", "DEBUG = True\\n")
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


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,  # mkdir -p behavior
    "openWorldHint": False,
  }
)
def create_directory(path: str) -> str:
  """Create a directory in the project

  Args:
      path: Directory path relative to project root

  Returns:
      Success message

  Use when:
  - Setting up project structure
  - Creating module directories
  - Organizing output files
  - Preparing for batch operations

  Behavior:
  - Creates parent directories automatically (mkdir -p)
  - Succeeds silently if directory already exists
  - Cannot convert existing file to directory

  Common errors:
  - FileExistsError: Path exists as a file
    → Delete or rename the file first
  - PermissionError: Cannot create in parent directory
    → Check parent directory permissions

  Example: create_directory("src/components/widgets")
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


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": True,  # Source is removed
    "idempotentHint": False,
    "openWorldHint": False,
  }
)
def move_file(source: str, destination: str) -> dict:
  """Move or rename a file or directory

  Args:
      source: Source path relative to project root
      destination: Destination path relative to project root

  Returns:
      Dict with status and paths

  Use when:
  - Renaming files or directories
  - Reorganizing project structure
  - Moving generated files to final location
  - Implementing refactoring operations

  Behavior:
  - Atomic operation (source removed only after successful copy)
  - Creates destination parent directories if needed
  - When destination is directory, moves file into it
  - Preserves file attributes and timestamps

  Side effects:
  - Source path no longer exists after success
  - May break imports or references to moved files
  - Git will show as delete + add (use git mv for tracking)

  Return format:
  - Success: {"status": "success", "source": "old/path", "destination": "new/path"}
  - Error: {"status": "error", "error": "Description of issue"}

  Examples:
  - Rename: move_file("old_name.py", "new_name.py")
  - Relocate: move_file("src/temp.py", "src/utils/helper.py")
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


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,  # Already deleted is not an error
    "openWorldHint": False,
  }
)
def delete_file(path: str) -> dict:
  """Delete a file or directory

  Args:
      path: Path to delete relative to project root

  Returns:
      Dict with status and deleted path

  Use when:
  - Removing temporary files
  - Cleaning build artifacts
  - Deleting obsolete code
  - Restructuring project

  Safety features:
  - Cannot delete project root
  - Cannot delete .git directory
  - Cannot delete .venv directory
  - Confirms path exists before deletion

  Behavior:
  - Recursively deletes directories and contents
  - No confirmation prompt (immediate deletion)
  - Returns error if path not found (idempotent)

  Immediate effects:
  - File/directory permanently removed
  - No built-in recovery mechanism
  - May affect running processes using the file

  Example: delete_file("temp/cache.json")
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


@mcp.tool(
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # Source remains
    "idempotentHint": False,  # Fails if destination exists
    "openWorldHint": False,
  }
)
def copy_file(source: str, destination: str) -> dict:
  """Copy a file or directory

  Args:
      source: Source path relative to project root
      destination: Destination path relative to project root

  Returns:
      Dict with status and paths

  Use when:
  - Creating backups before modifications
  - Duplicating templates or boilerplate
  - Preserving original while experimenting
  - Setting up test fixtures

  Behavior:
  - Source remains unchanged
  - Recursively copies directories
  - Preserves file attributes and timestamps
  - Fails if destination already exists
  - Creates parent directories as needed

  Not suitable for:
  - Very large files (blocks during copy)
  - Cross-filesystem operations (may be slow)
  - Files being actively written

  Return format:
  - Success: {"status": "success", "source": "path", "destination": "path"}
  - Error: {"status": "error", "error": "Reason"}

  Example: copy_file("config/prod.py", "config/dev.py")
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
