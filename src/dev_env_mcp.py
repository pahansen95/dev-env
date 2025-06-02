#!/usr/bin/env python3
"""
MCP Project Integration - CLI Tool for connecting Claude Desktop to local projects
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import ast
import difflib
import shutil
import re
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def add_file_logging(log_file):
  """Add file handler to existing logger"""
  # Create log directory if needed
  log_path = Path(log_file)
  log_path.parent.mkdir(parents=True, exist_ok=True)

  # Create file handler with same format
  file_handler = logging.FileHandler(log_file, mode="a")
  file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
  file_handler.setLevel(logging.DEBUG)  # Capture all levels

  # Add to root logger to capture all logs
  root_logger = logging.getLogger()
  root_logger.addHandler(file_handler)

  # Force immediate write
  logger.info(f"=== MCP Server Started - PID: {os.getpid()} ===")
  file_handler.flush()


# Utility functions for git operations
def run_git_command(args, cwd=None):
  """Run a git command and return output"""
  result = subprocess.run(
    ["git"] + args,
    capture_output=True,
    text=True,
    cwd=cwd,
    check=True,  # Fail fast on git errors
  )
  return result.stdout.strip()


def find_git_root():
  """Find the git project root directory"""
  return Path(run_git_command(["rev-parse", "--show-toplevel"]))


def get_git_project_name():
  """Get project name from git (remote origin or directory name)"""
  # Try to get from remote origin
  try:
    remote_url = run_git_command(["config", "--get", "remote.origin.url"])
    # Extract project name from URL
    if remote_url.endswith(".git"):
      remote_url = remote_url[:-4]

    # Get the last part of the URL
    project_name = remote_url.split("/")[-1]
    if ":" in project_name:  # SSH URL format
      project_name = project_name.split(":")[-1]

    return project_name
  except subprocess.CalledProcessError:
    # No remote, use directory name
    return find_git_root().name


# Create MCP server instance
try:
  git_project_name = get_git_project_name()
  server_display_name = f"Project: {git_project_name}"
except subprocess.CalledProcessError:
  # Not in a git repo yet, use generic name
  server_display_name = "Project Integration"

mcp = FastMCP(server_display_name)


# Path validation helper
def get_safe_path(path_str, must_exist=False):
  """Validate and return a safe path within the git project"""
  git_root = find_git_root()
  target_path = (git_root / path_str).resolve()

  # Ensure path is within project
  target_path.relative_to(git_root)

  # Check existence if required
  if must_exist:
    target_path.stat()

  return target_path


# Replace the hello_world tool with this status implementation


@mcp.tool()
def status() -> dict:
  """Get project health status and basic information"""
  logger.info("status tool called")

  status_info = {"health": "ok", "timestamp": datetime.utcnow().isoformat() + "Z", "errors": []}

  try:
    # Basic git information
    git_root = find_git_root()
    status_info["project"] = {"name": get_git_project_name(), "root": str(git_root), "root_exists": git_root.exists()}

    # Git status
    try:
      branch = run_git_command(["branch", "--show-current"])
      commit = run_git_command(["rev-parse", "--short", "HEAD"])

      # Check for uncommitted changes
      git_status = run_git_command(["status", "--porcelain"])
      is_clean = len(git_status) == 0

      status_info["git"] = {
        "branch": branch,
        "commit": commit,
        "clean": is_clean,
        "changes": len(git_status.splitlines()) if git_status else 0,
      }
    except subprocess.CalledProcessError as e:
      status_info["errors"].append(f"Git error: {str(e)}")
      status_info["git"] = {"error": "Unable to get git status"}

    # Python environment check
    venv_path = git_root / ".venv"
    status_info["environment"] = {
      "python": sys.version.split()[0],
      "venv_exists": venv_path.exists(),
      "venv_active": sys.prefix == str(venv_path),
    }

    # Basic project structure
    readme_exists = (git_root / "README.md").exists()
    src_exists = (git_root / "src").exists()

    status_info["structure"] = {
      "has_readme": readme_exists,
      "has_src": src_exists,
      "python_files": len(list(git_root.glob("**/*.py"))),
    }

  except subprocess.CalledProcessError:
    status_info["health"] = "error"
    status_info["errors"].append("Not in a git repository")
  except Exception as e:
    status_info["health"] = "error"
    status_info["errors"].append(f"Unexpected error: {str(e)}")
    logger.exception("Error in status tool")

  # Set health to warning if there are non-fatal errors
  if status_info["errors"] and status_info["health"] == "ok":
    status_info["health"] = "warning"

  return status_info


# Filesystem Operations
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
def find_files(pattern: str = "*", directory: str = ".") -> list[str]:
  """Find files matching a pattern in the project"""
  logger.info(f"find_files called with pattern='{pattern}' in directory='{directory}'")
  search_dir = get_safe_path(directory, must_exist=True)
  git_root = find_git_root()

  # Use rglob for recursive search if pattern contains '**'
  if "**" in pattern:
    matches = search_dir.rglob(pattern.replace("**/", ""))
  else:
    matches = search_dir.glob(pattern)

  files = [str(m.relative_to(git_root)) for m in matches if m.is_file()]
  logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
  return sorted(files)


# Discovery Operations
@mcp.tool()
def find_pattern_in_files(pattern: str, file_pattern: str = "**/*.py", max_files: int = 100) -> dict[str, list[str]]:
  """Find a pattern in files matching the given file pattern"""
  logger.info(f"find_pattern_in_files called with pattern='{pattern}', file_pattern='{file_pattern}'")

  git_root = find_git_root()
  results = {}
  files_searched = 0

  for file_path in git_root.rglob(file_pattern.replace("**/", "")):
    if files_searched >= max_files:
      results["warning"] = f"Stopped after searching {max_files} files"
      break

    if not file_path.is_file():
      continue

    files_searched += 1

    try:
      content = file_path.read_text(encoding="utf-8")
      matches = []

      for line_num, line in enumerate(content.splitlines(), 1):
        if pattern in line:
          matches.append(f"{line_num}: {line.strip()}")

      if matches:
        results[str(file_path.relative_to(git_root))] = matches

    except Exception:
      # Skip files that can't be read (binary, permissions, etc)
      continue

  logger.info(f"Searched {files_searched} files, found pattern in {len(results)} files")
  return results


@mcp.tool()
def find_by_name(name: str, type: str = "both") -> list[str]:
  """Find files or folders by name. Type can be 'file', 'dir', or 'both'"""
  logger.info(f"find_by_name called with name='{name}', type='{type}'")

  if type not in ["file", "dir", "both"]:
    raise ValueError("type must be 'file', 'dir', or 'both'")

  git_root = find_git_root()
  results = []

  for path in git_root.rglob(f"*{name}*"):
    relative_path = str(path.relative_to(git_root))

    if type == "file" and path.is_file():
      results.append(relative_path)
    elif type == "dir" and path.is_dir():
      results.append(relative_path + "/")
    elif type == "both":
      results.append(relative_path + ("/" if path.is_dir() else ""))

  logger.info(f"Found {len(results)} items matching '{name}'")
  return sorted(results)


# Complete Filesystem CRUD Operations
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


# Git Integration Tools
@mcp.tool()
def git_status() -> dict:
  """Get detailed git repository status"""
  logger.info("git_status called")

  try:
    # Get current branch
    branch = run_git_command(["branch", "--show-current"])

    # Get status information
    status_output = run_git_command(["status", "--porcelain=v1"])

    # Parse status output
    staged = []
    modified = []
    untracked = []

    for line in status_output.splitlines():
      if not line:
        continue
      status_code = line[:2]
      file_path = line[3:]

      if status_code[0] in "AM":  # Added or Modified in index
        staged.append(file_path)
      if status_code[1] == "M":  # Modified in working tree
        modified.append(file_path)
      if status_code == "??":  # Untracked
        untracked.append(file_path)

    # Get commit info
    commit = run_git_command(["rev-parse", "--short", "HEAD"])

    return {
      "branch": branch,
      "commit": commit,
      "staged": staged,
      "modified": modified,
      "untracked": untracked,
      "clean": len(staged) == 0 and len(modified) == 0 and len(untracked) == 0,
    }
  except Exception as e:
    logger.error(f"Failed to get git status: {e}")
    return {"error": str(e)}


@mcp.tool()
def git_commit(message: str, files: list[str] = None) -> dict:
  """Create a git commit"""
  logger.info(f"git_commit called with message: {message}")

  try:
    # Stage files if specified
    if files:
      for file in files:
        run_git_command(["add", file])

    # Create commit
    run_git_command(["commit", "-m", message])

    # Get new commit info
    commit_hash = run_git_command(["rev-parse", "--short", "HEAD"])

    return {"status": "success", "commit": commit_hash, "message": message}
  except subprocess.CalledProcessError as e:
    logger.error(f"Failed to commit: {e}")
    return {"status": "error", "error": str(e), "stderr": e.stderr}


@mcp.tool()
def git_log(max_count: int = 10) -> list[dict]:
  """Get git commit history"""
  logger.info(f"git_log called with max_count={max_count}")

  try:
    # Get log with custom format
    log_format = "%H|%h|%an|%ae|%ad|%s"
    log_output = run_git_command(["log", f"--max-count={max_count}", f"--format={log_format}", "--date=iso"])

    commits = []
    for line in log_output.splitlines():
      if not line:
        continue
      parts = line.split("|", 5)
      if len(parts) >= 6:
        commits.append(
          {
            "hash": parts[0],
            "short_hash": parts[1],
            "author": parts[2],
            "email": parts[3],
            "date": parts[4],
            "message": parts[5],
          }
        )

    return commits
  except Exception as e:
    logger.error(f"Failed to get git log: {e}")
    return [{"error": str(e)}]


@mcp.tool()
def git_diff(file: str = None, staged: bool = False) -> str:
  """Get git diff output"""
  logger.info(f"git_diff called for file={file}, staged={staged}")

  try:
    args = ["diff"]

    if staged:
      args.append("--cached")

    if file:
      args.append(file)

    diff_output = run_git_command(args)
    return diff_output if diff_output else "No differences found"

  except Exception as e:
    logger.error(f"Failed to get diff: {e}")
    return f"Error: {str(e)}"


# Development Tools for Surgical Code Modifications


def validate_syntax(file_path: Path) -> dict:
  """Validate file syntax based on extension

  Returns dict with:
      - valid: bool (True if syntax is valid)
      - status: 'valid', 'invalid', or 'skipped'
      - message: Description of validation result
      - errors: List of syntax errors if any
  """
  extension = file_path.suffix.lower()

  # Python files
  if extension == ".py":
    try:
      content = file_path.read_text()
      ast.parse(content, filename=str(file_path))
      return {"valid": True, "status": "valid", "message": "Python syntax is valid"}
    except SyntaxError as e:
      return {
        "valid": False,
        "status": "invalid",
        "message": f"Python syntax error at line {e.lineno}",
        "errors": [f"Line {e.lineno}: {e.msg}"],
      }

  # JSON files
  elif extension == ".json":
    try:
      content = file_path.read_text()
      json.loads(content)
      return {"valid": True, "status": "valid", "message": "JSON syntax is valid"}
    except json.JSONDecodeError as e:
      return {
        "valid": False,
        "status": "invalid",
        "message": f"JSON syntax error at line {e.lineno}",
        "errors": [f"Line {e.lineno}, Column {e.colno}: {e.msg}"],
      }

  # Unsupported file types
  else:
    return {
      "valid": True,  # Assume valid since we can't check
      "status": "skipped",
      "message": f"Syntax validation not supported for {extension} files",
    }


@mcp.tool()
def apply_patch(file_path: str, patch: str) -> dict:
  """Apply a unified diff patch to a file using difflib

  Args:
      file_path: Path to file to patch
      patch: Unified diff format patch string

  Returns:
      dict with status, backup_path, and any errors
  """
  logger.info(f"apply_patch called for {file_path}")

  try:
    # Validate and resolve path
    target_path = get_safe_path(file_path, must_exist=True)

    # Create backup first
    backup_name = f".{target_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    backup_path = target_path.parent / backup_name
    backup_path.write_bytes(target_path.read_bytes())

    # Read current content
    original_content = target_path.read_text()
    original_lines = original_content.splitlines(keepends=True)

    # Use difflib.restore to apply the patch
    # Since difflib doesn't have direct patch application, we'll use a robust approach
    patch_lines = patch.splitlines(keepends=True)

    # Parse hunks with proper offset tracking
    hunks = []
    current_hunk = None
    hunk_header_re = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    for line in patch_lines:
      match = hunk_header_re.match(line)
      if match:
        if current_hunk:
          hunks.append(current_hunk)

        old_start = int(match.group(1))
        old_count = int(match.group(2) or 1)
        new_start = int(match.group(3))
        new_count = int(match.group(4) or 1)

        current_hunk = {
          "old_start": old_start,
          "old_count": old_count,
          "new_start": new_start,
          "new_count": new_count,
          "old_lines": [],
          "new_lines": [],
        }
      elif current_hunk is not None:
        if line.startswith("-") and not line.startswith("---"):
          current_hunk["old_lines"].append(line[1:])
        elif line.startswith("+") and not line.startswith("+++"):
          current_hunk["new_lines"].append(line[1:])
        elif line.startswith(" "):
          current_hunk["old_lines"].append(line[1:])
          current_hunk["new_lines"].append(line[1:])

    if current_hunk:
      hunks.append(current_hunk)

    # Apply hunks from bottom to top to preserve line numbers
    result_lines = original_lines.copy()
    lines_changed = 0

    for hunk in reversed(hunks):
      start_idx = hunk["old_start"] - 1
      end_idx = start_idx + hunk["old_count"]

      # Verify context matches
      expected_lines = hunk["old_lines"]
      actual_lines = result_lines[start_idx:end_idx]

      # Compare without worrying about newline differences
      expected_content = "".join(expected_lines)
      actual_content = "".join(actual_lines)

      if expected_content.strip() != actual_content.strip():
        # Try fuzzy matching using difflib
        matcher = difflib.SequenceMatcher(None, actual_content, expected_content)
        if matcher.ratio() < 0.8:  # Less than 80% similarity
          raise ValueError(f"Patch context doesn't match at line {hunk['old_start']}")

      # Apply the change
      result_lines[start_idx:end_idx] = hunk["new_lines"]
      lines_changed += len(hunk["old_lines"]) + len(hunk["new_lines"])

    # Write patched content
    patched_content = "".join(result_lines)
    target_path.write_text(patched_content)

    # Validate syntax after patching
    validation = validate_syntax(target_path)

    return {
      "status": "success",
      "backup_path": str(backup_path.relative_to(find_git_root())),
      "lines_changed": lines_changed,
      "syntax_validation": validation,
    }

  except Exception as e:
    logger.error(f"Failed to apply patch: {e}")
    # Restore from backup on error
    if "backup_path" in locals() and backup_path.exists():
      try:
        target_path.write_bytes(backup_path.read_bytes())
        logger.info("Restored file from backup")
      except Exception as restore_error:
        logger.error(f"Failed to restore backup: {restore_error}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def edit_lines(file_path: str, start_line: int, end_line: int, replacement: str) -> dict:
  """Replace specific line range in a file (1-indexed)

  Args:
      file_path: Path to file to edit
      start_line: Starting line number (inclusive, 1-indexed)
      end_line: Ending line number (inclusive, 1-indexed)
      replacement: Text to replace the line range with

  Returns:
      dict with status and details
  """
  logger.info(f"edit_lines called for {file_path} lines {start_line}-{end_line}")

  try:
    # Validate path
    target_path = get_safe_path(file_path, must_exist=True)

    # Read file
    content = target_path.read_text()
    lines = content.splitlines(keepends=True)

    # Validate line numbers
    if start_line < 1 or end_line < start_line:
      raise ValueError("Invalid line range")
    if end_line > len(lines):
      raise ValueError(f"End line {end_line} exceeds file length {len(lines)}")

    # Create backup
    backup_name = f".{target_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    backup_path = target_path.parent / backup_name
    backup_path.write_text(content)

    # Prepare replacement lines
    replacement_lines = replacement.splitlines(keepends=True)
    if replacement and not replacement.endswith("\n"):
      replacement_lines[-1] += "\n"

    # Perform replacement
    new_lines = lines[: start_line - 1] + replacement_lines + lines[end_line:]

    # Write result
    target_path.write_text("".join(new_lines))

    return {
      "status": "success",
      "backup_path": str(backup_path.relative_to(find_git_root())),
      "lines_replaced": end_line - start_line + 1,
      "new_line_count": len(replacement_lines),
    }

  except Exception as e:
    logger.error(f"Failed to edit lines: {e}")
    return {"status": "error", "error": str(e)}


@mcp.tool()
def find_pattern_regex(
  pattern: str, file_pattern: str = "**/*", max_files: int = 100, context_lines: int = 2
) -> list[dict]:
  """Find regex patterns in files with context

  Args:
      pattern: Regular expression pattern to search for
      file_pattern: Glob pattern for files to search
      max_files: Maximum number of files to search
      context_lines: Number of context lines before/after match

  Returns:
      List of matches with file path, line number, match text, and context
  """
  logger.info(f"find_pattern_regex called with pattern='{pattern}', file_pattern='{file_pattern}'")

  try:
    regex = re.compile(pattern)
  except re.error as e:
    logger.error(f"Invalid regex pattern: {e}")
    return [{"error": f"Invalid regex pattern: {str(e)}"}]

  git_root = find_git_root()
  results = []
  files_searched = 0

  for file_path in git_root.rglob(file_pattern.replace("**/", "")):
    if files_searched >= max_files:
      break

    if not file_path.is_file():
      continue

    files_searched += 1

    try:
      content = file_path.read_text(encoding="utf-8")
      lines = content.splitlines()

      for line_num, line in enumerate(lines, 1):
        match = regex.search(line)
        if match:
          # Get context lines
          start = max(0, line_num - context_lines - 1)
          end = min(len(lines), line_num + context_lines)
          context = lines[start:end]

          results.append(
            {
              "file": str(file_path.relative_to(git_root)),
              "line": line_num,
              "match": match.group(0),
              "full_line": line.strip(),
              "context": "\n".join(f"{start + i + 1}: {l}" for i, l in enumerate(context)),
            }
          )

    except (UnicodeDecodeError, PermissionError):
      # Skip binary files or files we can't read
      continue

  logger.info(f"Searched {files_searched} files, found {len(results)} matches")
  return results


@mcp.tool()
def find_code_definition(name: str, definition_type: str = "any", file_pattern: str = "**/*.py") -> list[dict]:
  """Find function or class definitions in Python files

  Args:
      name: Name of function/class to find
      definition_type: 'function', 'class', or 'any'
      file_pattern: Glob pattern for files to search

  Returns:
      List of matches with file path, line number, and preview
  """
  logger.info(f"find_code_definition called for '{name}' type={definition_type}")

  results = []
  git_root = find_git_root()

  # Search Python files
  for file_path in git_root.rglob(file_pattern.replace("**/", "")):
    if not file_path.is_file():
      continue

    try:
      content = file_path.read_text()
      tree = ast.parse(content, filename=str(file_path))

      # Walk AST to find definitions
      for node in ast.walk(tree):
        match = False
        node_type = None

        if definition_type in ("function", "any") and isinstance(node, ast.FunctionDef):
          if node.name == name:
            match = True
            node_type = "function"

        elif definition_type in ("class", "any") and isinstance(node, ast.ClassDef):
          if node.name == name:
            match = True
            node_type = "class"

        if match and hasattr(node, "lineno"):
          # Get preview lines
          lines = content.splitlines()
          start = max(0, node.lineno - 1)
          end = min(len(lines), node.lineno + 4)
          preview = lines[start:end]

          results.append(
            {
              "file": str(file_path.relative_to(git_root)),
              "line": node.lineno,
              "type": node_type,
              "name": node.name,
              "preview": "\n".join(preview),
            }
          )

    except SyntaxError:
      # Skip files with syntax errors
      logger.debug(f"Syntax error in {file_path}, skipping")
      continue
    except Exception as e:
      logger.debug(f"Error parsing {file_path}: {e}")
      continue

  logger.info(f"Found {len(results)} definitions of '{name}'")
  return results


# CLI Commands
def install_command(args):
  """Install the MCP server in Claude Desktop"""
  logger.info("Starting Claude Desktop installation")

  # Find git project root - fail if not in git repo
  project_root = find_git_root()
  logger.info(f"Found git project root: {project_root}")

  # Check for .venv in project root
  venv_path = project_root / ".venv"
  if not venv_path.is_dir():
    raise FileNotFoundError(
      f"No .venv directory found at {project_root}\nPlease create a virtual environment with: python -m venv .venv"
    )

  # Get project name from git
  git_project_name = get_git_project_name()
  logger.info(f"Detected project name from git: {git_project_name}")

  # Get Claude Desktop config path
  if sys.platform == "darwin":  # macOS
    config_dir = Path.home() / "Library" / "Application Support" / "Claude"
  elif sys.platform.startswith("linux"):
    xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    config_dir = Path(xdg_config) / "Claude"
  else:
    raise OSError(f"Unsupported platform: {sys.platform}")

  if not config_dir.exists():
    raise FileNotFoundError(
      f"Claude Desktop config directory not found: {config_dir}\n"
      "Please ensure Claude Desktop is installed and run at least once"
    )

  config_file = config_dir / "claude_desktop_config.json"
  logger.info(f"Claude config file: {config_file}")

  # Load existing config or create new one
  if config_file.exists():
    with open(config_file, "r") as f:
      config = json.load(f)
    logger.info("Loaded existing Claude config")
  else:
    config = {}

  # Ensure mcpServers section exists
  if "mcpServers" not in config:
    config["mcpServers"] = {}

  # Get the current script path
  script_path = Path(sys.argv[0]).resolve()

  # Configure the server entry
  server_name = args.name or git_project_name

  # Determine Python executable path based on platform
  if sys.platform == "win32":
    python_executable = project_root / ".venv" / "Scripts" / "python.exe"
  else:
    python_executable = project_root / ".venv" / "bin" / "python"

  server_config = {"command": str(python_executable), "args": [str(script_path)], "cwd": str(project_root)}

  # Add dev mode configuration
  if args.dev:
    logger.info("Configuring server for development mode")
    # Add verbose flag and log file before run command
    log_file_path = project_root / ".cache" / "mcp.log"
    server_config["args"].extend(
      [
        "-v",  # Verbose logging
        "-l",
        str(log_file_path),  # Log to file
      ]
    )
    logger.info(f"Development logs will be written to: {log_file_path}")

  # Add run subcommand after global flags
  server_config["args"].extend(["run", str(project_root)])

  # Add environment variables if needed
  if args.env:
    server_config["env"] = dict(env.split("=", 1) for env in args.env)

  config["mcpServers"][server_name] = server_config

  # Write updated config
  with open(config_file, "w") as f:
    json.dump(config, f, indent=2)

  logger.info(f"Successfully installed server '{server_name}' in Claude Desktop")
  logger.info(f"Using Python from: {server_config['command']}")
  logger.info(f"Working directory: {server_config['cwd']}")
  logger.info(f"Git project: {git_project_name}")


def run_command(args):
  """Run the MCP server"""
  logger.info("Starting MCP server")
  logger.info(f"Initial working directory: {os.getcwd()}")
  logger.info(f"Python executable: {sys.executable}")

  # Change to project directory
  project_dir = Path(args.project_dir).resolve()
  if not project_dir.exists():
    raise FileNotFoundError(f"Project directory not found: {project_dir}")

  os.chdir(project_dir)
  logger.info(f"Changed working directory to: {os.getcwd()}")

  # Verify we're in a git repository
  try:
    git_root = find_git_root()
    logger.info(f"Git project root: {git_root}")
    git_name = get_git_project_name()
    logger.info(f"Git project name: {git_name}")
  except subprocess.CalledProcessError:
    raise RuntimeError(f"Directory is not a git repository: {project_dir}")

  # Set log level based on verbosity
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("Debug logging enabled")

  # Run with stdio transport - let exceptions bubble up
  logger.info("Starting stdio transport")
  mcp.run(transport="stdio")


def validate_command(args):
  """Validate the MCP server configuration and syntax"""
  logger.info("Validating MCP server")

  # If we got here, imports worked and syntax is valid
  try:
    # Quick validation - just check if we can access the MCP server instance
    logger.info(f"MCP server name: {mcp.name}")
    logger.info("✓ Validation successful - server configuration is valid")
  except Exception as e:
    logger.error(f"Validation failed: {e}")
    sys.exit(1)


def main():
  """Main CLI entry point"""
  parser = argparse.ArgumentParser(description="MCP Project Integration - Connect Claude Desktop to local projects")

  # Global options
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
  parser.add_argument("-l", "--log-file", help="Duplicate logs to specified file")

  # Subcommands
  subparsers = parser.add_subparsers(dest="command", help="Available commands")

  # Install command
  install_parser = subparsers.add_parser("install", help="Install the MCP server in Claude Desktop")
  install_parser.add_argument("-n", "--name", help="Server name in Claude Desktop (default: git project name)")
  install_parser.add_argument("-e", "--env", action="append", help="Environment variables (format: KEY=VALUE)")
  install_parser.add_argument(
    "--dev", action="store_true", help="Install in development mode with verbose logging to .cache/mcp.log"
  )

  # Run command
  run_parser = subparsers.add_parser("run", help="Run the MCP server")
  run_parser.add_argument("project_dir", help="Project directory to serve from")

  # Validate command
  validate_parser = subparsers.add_parser("validate", help="Validate the MCP server syntax and configuration")

  args = parser.parse_args()

  # Configure logging based on arguments
  if args.log_file:
    add_file_logging(args.log_file)
    logger.info(f"Logging to file: {args.log_file}")

  # Set verbosity
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  # Execute command
  try:
    if args.command == "install":
      install_command(args)
    elif args.command == "validate":
      validate_command(args)
    elif args.command == "run":
      run_command(args)
    else:
      parser.print_help()
      sys.exit(1)
  except KeyboardInterrupt:
    logger.info("Interrupted by user")
    sys.exit(130)  # Standard exit code for SIGINT
  except Exception as e:
    logger.error(f"{type(e).__name__}: {e}")
    if args.verbose:
      logger.exception("Full traceback:")
    sys.exit(1)


if __name__ == "__main__":
  sys.exit(main())
