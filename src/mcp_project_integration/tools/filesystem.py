"""File system operations and management tools"""

import logging
import shutil

from ..server import mcp
from ..core import get_safe_path, find_git_root, document_tool

logger = logging.getLogger(__name__)


TOOL_PREFIX = "file"


@document_tool(
  name="file_read",
  purpose="Safely read text files within project boundaries",
  category="File Operations",
  operational_model="""
  Validates path within project root, reads entire file content,
  and returns as UTF-8 string. Fails fast on encoding errors.
  """,
  usage_scenarios=[
    {"condition": "Reading configuration files", "rationale": "Enforces project boundaries and UTF-8 validation"},
    {"condition": "Inspecting source code", "rationale": "Returns full content for analysis or modification"},
    {"condition": "Loading templates or data files", "rationale": "Provides safe access within project scope"},
  ],
  anti_patterns=[
    {
      "condition": "Binary file processing",
      "reason": "Enforces UTF-8 encoding",
      "alternative": "Use dedicated binary handlers",
    },
    {
      "condition": "Files larger than 100MB",
      "reason": "Loads entire file into memory",
      "alternative": "Use streaming file readers",
    },
  ],
  examples=[
    {
      "title": "Read configuration",
      "code": "config = file_read('settings.json')",
      "explanation": "Simple file reading for configuration",
      "complexity": 1,
    },
    {
      "title": "Read with fallback",
      "code": """try:
    content = file_read('config.json')
except FileNotFoundError:
    content = file_read('config.default.json')""",
      "explanation": "Fallback pattern for optional files",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "FileNotFoundError",
      "cause": "Path doesn't exist",
      "diagnosis": "Run search_files('*.json') to find available files",
      "recovery": "Create file or correct path",
      "state_impact": "No changes - read-only operation",
    },
    {
      "error_type": "IsADirectoryError",
      "cause": "Path points to directory",
      "diagnosis": "Use search_files to explore directory contents",
      "recovery": "Specify file within directory",
      "state_impact": "No changes - read-only operation",
    },
    {
      "error_type": "ValueError",
      "cause": "File is not UTF-8 encoded",
      "diagnosis": "File may be binary or use different encoding",
      "recovery": "Convert file to UTF-8 or use appropriate handler",
      "state_impact": "No changes - read-only operation",
    },
  ],
  performance={
    "time_complexity": "O(n) with file size",
    "memory_usage": "Full file loaded into memory",
    "concurrency": "Thread-safe, multiple reads allowed",
  },
  see_also={"file_write": "Write content back after modifications", "search_files": "Discover available files first"},
  composition=["search_files → file_read → file_write", "file_read → patch_apply"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_read", annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True}
)
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


@document_tool(
  name="file_write",
  purpose="Write or overwrite text files with automatic parent directory creation",
  category="File Operations",
  operational_model="""
  Validates path within project boundaries, creates parent directories if needed,
  then writes content as UTF-8. Overwrites existing files without confirmation.
  """,
  usage_scenarios=[
    {"condition": "Creating new source files", "rationale": "Automatic parent directory creation simplifies workflows"},
    {"condition": "Updating configuration files", "rationale": "Direct overwrite for programmatic updates"},
    {"condition": "Generating code or documentation", "rationale": "Reliable output with consistent encoding"},
  ],
  anti_patterns=[
    {
      "condition": "Preserving existing content",
      "reason": "Overwrites without warning",
      "alternative": "Read existing content first if merging needed",
    },
    {
      "condition": "Writing to system directories",
      "reason": "Enforces project boundaries",
      "alternative": "Only write within project root",
    },
  ],
  examples=[
    {
      "title": "Create Python module",
      "code": 'file_write("src/utils.py", "def helper():\\n    pass\\n")',
      "explanation": "Creates file with parent directories",
      "complexity": 1,
    },
    {
      "title": "Update configuration",
      "code": """import json
config = {"debug": True, "port": 8080}
file_write("config.json", json.dumps(config, indent=2))""",
      "explanation": "Write structured data as JSON",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "IsADirectoryError",
      "cause": "Path exists as directory",
      "diagnosis": "Check path with search_files",
      "recovery": "Choose different filename or delete directory",
      "state_impact": "No file written",
    },
    {
      "error_type": "PermissionError",
      "cause": "Insufficient write permissions",
      "diagnosis": "Check file ownership and permissions",
      "recovery": "Fix permissions or choose different location",
      "state_impact": "No file written",
    },
  ],
  performance={
    "time_complexity": "O(n) with content size",
    "memory_usage": "Full content in memory",
    "concurrency": "Not thread-safe for same file",
  },
  see_also={
    "file_read": "Read existing content before overwriting",
    "file_create_directory": "Create directory structure explicitly",
  },
  composition=["file_read → (modify) → file_write", "search_files → file_write"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_write",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # Creates/overwrites but doesn't delete
    "idempotentHint": False,  # Overwrites existing content
    "openWorldHint": False,
  },
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


@document_tool(
  name="file_create_directory",
  purpose="Create directory structures with automatic parent creation",
  category="File Operations",
  operational_model="""
  Creates the specified directory and all parent directories if they don't exist.
  Idempotent operation that succeeds if directory already exists.
  """,
  usage_scenarios=[
    {"condition": "Setting up project structure", "rationale": "Creates entire path hierarchy in one operation"},
    {"condition": "Preparing output directories", "rationale": "Ensures destination exists before file operations"},
    {"condition": "Organizing generated content", "rationale": "Idempotent behavior allows repeated calls"},
  ],
  anti_patterns=[
    {
      "condition": "Converting file to directory",
      "reason": "Cannot replace existing file",
      "alternative": "Delete or rename file first",
    }
  ],
  examples=[
    {
      "title": "Create module structure",
      "code": "file_create_directory('src/components/widgets')",
      "explanation": "Creates nested directory hierarchy",
      "complexity": 1,
    },
    {
      "title": "Prepare output directory",
      "code": """file_create_directory('output/reports/2024')
file_write('output/reports/2024/summary.txt', report_content)""",
      "explanation": "Ensure directory exists before writing",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "FileExistsError",
      "cause": "Path exists as a file",
      "diagnosis": "Use search_files to check path type",
      "recovery": "Delete or rename the existing file",
      "state_impact": "No directory created",
    }
  ],
  performance={"time_complexity": "O(d) with directory depth", "memory_usage": "Minimal", "concurrency": "Thread-safe"},
  see_also={"file_write": "Create files after directory setup", "search_files": "Check existing structure"},
  composition=["file_create_directory → file_write"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_create_directory",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,  # mkdir -p behavior
    "openWorldHint": False,
  },
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


@document_tool(
  name="file_move",
  purpose="Move or rename files and directories within project",
  category="File Operations",
  operational_model="""
  Atomically moves source to destination, creating parent directories as needed.
  Source is removed only after successful copy. Preserves all attributes.
  """,
  usage_scenarios=[
    {"condition": "Renaming files or directories", "rationale": "Atomic operation ensures consistency"},
    {"condition": "Reorganizing project structure", "rationale": "Preserves timestamps and permissions"},
    {
      "condition": "Moving generated files to final location",
      "rationale": "Safe relocation with automatic directory creation",
    },
  ],
  anti_patterns=[
    {
      "condition": "Cross-repository moves",
      "reason": "Restricted to project boundaries",
      "alternative": "Use copy_file then delete_file",
    },
    {
      "condition": "Preserving Git history",
      "reason": "Shows as delete+add in Git",
      "alternative": "Use git mv command instead",
    },
  ],
  examples=[
    {
      "title": "Rename file",
      "code": "file_move('old_name.py', 'new_name.py')",
      "explanation": "Simple file rename in same directory",
      "complexity": 1,
    },
    {
      "title": "Reorganize module",
      "code": """file_move('utils.py', 'src/helpers/utils.py')
# Update imports in other files""",
      "explanation": "Move file to new location",
      "complexity": 2,
    },
    {
      "title": "Move into directory",
      "code": "file_move('script.py', 'scripts/')",
      "explanation": "Move file into existing directory",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "FileNotFoundError",
      "cause": "Source doesn't exist",
      "diagnosis": "Verify source path with search_files",
      "recovery": "Correct source path",
      "state_impact": "No changes made",
    },
    {
      "error_type": "File exists",
      "cause": "Destination already exists",
      "diagnosis": "Check destination with search_files",
      "recovery": "Choose different name or delete destination",
      "state_impact": "No changes made",
    },
  ],
  performance={
    "time_complexity": "O(1) on same filesystem",
    "memory_usage": "Minimal - metadata only",
    "concurrency": "Not safe for concurrent moves",
  },
  see_also={"file_copy": "Preserve source file", "file_delete": "Remove files instead"},
  composition=["search_files → file_move → file_write"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_move",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": True,  # Source is removed
    "idempotentHint": False,
    "openWorldHint": False,
  },
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


@document_tool(
  name="file_delete",
  purpose="Permanently remove files or directories with safety checks",
  category="File Operations",
  operational_model="""
  Recursively deletes files or directories after safety validation.
  Prevents deletion of critical directories (.git, .venv, project root).
  Idempotent - returns success if already deleted.
  """,
  usage_scenarios=[
    {"condition": "Removing temporary files", "rationale": "Clean up after processing"},
    {"condition": "Deleting build artifacts", "rationale": "Reset to clean state"},
    {"condition": "Removing obsolete code", "rationale": "Maintain clean project structure"},
  ],
  anti_patterns=[
    {
      "condition": "Deleting without backup",
      "reason": "No built-in recovery",
      "alternative": "Use file_copy to backup first",
    },
    {
      "condition": "Deleting active files",
      "reason": "May crash running processes",
      "alternative": "Ensure files aren't in use",
    },
  ],
  examples=[
    {
      "title": "Remove temporary file",
      "code": "file_delete('temp/cache.json')",
      "explanation": "Delete single file",
      "complexity": 1,
    },
    {
      "title": "Clean build directory",
      "code": """file_delete('build/')
file_create_directory('build/')""",
      "explanation": "Remove and recreate directory",
      "complexity": 2,
    },
    {
      "title": "Safe cleanup pattern",
      "code": """if file_delete('output.tmp')['status'] == 'success':
    print('Cleanup successful')""",
      "explanation": "Check deletion status",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Critical directory",
      "cause": "Attempting to delete .git, .venv, or root",
      "diagnosis": "Safety check prevented deletion",
      "recovery": "This is intentional - no recovery needed",
      "state_impact": "No deletion performed",
    },
    {
      "error_type": "FileNotFoundError",
      "cause": "Path doesn't exist",
      "diagnosis": "Already deleted or never existed",
      "recovery": "No action needed - idempotent",
      "state_impact": "Returns error but safe",
    },
  ],
  performance={
    "time_complexity": "O(n) with file count",
    "memory_usage": "Minimal",
    "concurrency": "Not safe for concurrent deletes",
  },
  see_also={"file_copy": "Backup before deletion", "file_move": "Relocate instead of delete"},
  composition=["file_copy → file_delete", "file_delete → file_create_directory"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_delete",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": True,  # Already deleted is not an error
    "openWorldHint": False,
  },
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


@document_tool(
  name="file_copy",
  purpose="Create duplicates of files or directories preserving attributes",
  category="File Operations",
  operational_model="""
  Recursively copies source to destination, preserving timestamps and permissions.
  Fails if destination exists. Creates parent directories automatically.
  Source remains unchanged.
  """,
  usage_scenarios=[
    {"condition": "Creating backups before modifications", "rationale": "Preserve original for rollback"},
    {"condition": "Duplicating templates or boilerplate", "rationale": "Start from known-good configuration"},
    {"condition": "Setting up test fixtures", "rationale": "Create isolated test data"},
  ],
  anti_patterns=[
    {
      "condition": "Copying very large files",
      "reason": "Blocks during entire copy",
      "alternative": "Consider streaming or chunked copy",
    },
    {
      "condition": "Overwriting destinations",
      "reason": "Fails if destination exists",
      "alternative": "Delete destination first if needed",
    },
  ],
  examples=[
    {
      "title": "Backup configuration",
      "code": "file_copy('config.json', 'config.backup.json')",
      "explanation": "Create backup before changes",
      "complexity": 1,
    },
    {
      "title": "Duplicate template",
      "code": """file_copy('templates/module.py', 'src/new_module.py')
# Then customize the copy""",
      "explanation": "Start from template file",
      "complexity": 2,
    },
    {
      "title": "Copy entire directory",
      "code": """file_copy('src/component', 'src/component_v2')
# Work on v2 while preserving original""",
      "explanation": "Duplicate directory structure",
      "complexity": 2,
    },
  ],
  error_scenarios=[
    {
      "error_type": "Destination exists",
      "cause": "Target path already exists",
      "diagnosis": "Check with search_files",
      "recovery": "Choose different name or delete existing",
      "state_impact": "No copy performed",
    },
    {
      "error_type": "FileNotFoundError",
      "cause": "Source doesn't exist",
      "diagnosis": "Verify source with search_files",
      "recovery": "Correct source path",
      "state_impact": "No copy performed",
    },
  ],
  performance={
    "time_complexity": "O(n) with file size",
    "memory_usage": "Buffers during copy",
    "concurrency": "Safe for different files",
  },
  see_also={"file_move": "Relocate instead of duplicate", "file_read": "Read without copying"},
  composition=["file_copy → file_write → file_delete(original)"],
)
@mcp.tool(
  name=f"{TOOL_PREFIX}_copy",
  annotations={
    "readOnlyHint": False,
    "destructiveHint": False,  # Source remains
    "idempotentHint": False,  # Fails if destination exists
    "openWorldHint": False,
  },
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
