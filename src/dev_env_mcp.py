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


# Consolidated Discovery Operations


@mcp.tool()
def find(
  query: str,
  match_type: str = "glob",  # "glob", "name", "exact"
  target_type: str = "both",  # "file", "dir", "both"
  directory: str = ".",
) -> list[str]:
  """Find files and directories using various matching strategies

  Args:
      query: Search query (glob pattern, name substring, or exact name)
      match_type: Matching strategy - "glob" (wildcards), "name" (substring), or "exact"
      target_type: What to find - "file", "dir", or "both"
      directory: Starting directory for search (default: project root)

  Returns:
      List of matching paths relative to project root
  """
  logger.info(f"find called with query='{query}', match_type='{match_type}', target_type='{target_type}'")

  if match_type not in ["glob", "name", "exact"]:
    raise ValueError("match_type must be 'glob', 'name', or 'exact'")
  if target_type not in ["file", "dir", "both"]:
    raise ValueError("target_type must be 'file', 'dir', or 'both'")

  search_dir = get_safe_path(directory, must_exist=True)
  git_root = find_git_root()
  results = []

  # Glob pattern matching (replaces find_files)
  if match_type == "glob":
    # Use rglob for recursive search if pattern contains '**'
    if "**" in query:
      matches = search_dir.rglob(query.replace("**/", ""))
    else:
      matches = search_dir.glob(query)

    for path in matches:
      relative_path = str(path.relative_to(git_root))
      if target_type == "file" and path.is_file():
        results.append(relative_path)
      elif target_type == "dir" and path.is_dir():
        results.append(relative_path + "/")
      elif target_type == "both":
        results.append(relative_path + ("/" if path.is_dir() else ""))

  # Name substring matching (replaces find_by_name)
  elif match_type == "name":
    for path in search_dir.rglob("*"):
      if query in path.name:
        relative_path = str(path.relative_to(git_root))
        if target_type == "file" and path.is_file():
          results.append(relative_path)
        elif target_type == "dir" and path.is_dir():
          results.append(relative_path + "/")
        elif target_type == "both":
          results.append(relative_path + ("/" if path.is_dir() else ""))

  # Exact name matching
  elif match_type == "exact":
    for path in search_dir.rglob("*"):
      if path.name == query:
        relative_path = str(path.relative_to(git_root))
        if target_type == "file" and path.is_file():
          results.append(relative_path)
        elif target_type == "dir" and path.is_dir():
          results.append(relative_path + "/")
        elif target_type == "both":
          results.append(relative_path + ("/" if path.is_dir() else ""))

  logger.info(f"Found {len(results)} items matching query '{query}'")
  return sorted(results)


@mcp.tool()
def search(
  pattern: str,
  search_type: str = "string",  # "string", "regex", "ast"
  file_pattern: str = "**/*",
  max_files: int = 100,
  context_lines: int = 0,
  definition_type: str = None,  # For AST searches: "function", "class", or "any"
) -> list[dict]:
  """Universal search tool for finding patterns in project files

  Args:
      pattern: Search pattern (string, regex, or function/class name)
      search_type: Type of search - "string", "regex", or "ast" (for Python definitions)
      file_pattern: Glob pattern for files to search (default: all files)
      max_files: Maximum number of files to search
      context_lines: Number of context lines before/after match (for string/regex)
      definition_type: For AST search - "function", "class", or "any" (default: "any")

  Returns:
      List of matches with file path, line number, and match details
  """
  logger.info(f"search called with pattern='{pattern}', search_type='{search_type}', file_pattern='{file_pattern}'")

  if search_type not in ["string", "regex", "ast"]:
    raise ValueError("search_type must be 'string', 'regex', or 'ast'")

  git_root = find_git_root()
  results = []
  files_searched = 0

  # AST-based search for Python code definitions
  if search_type == "ast":
    if definition_type is None:
      definition_type = "any"

    # Only search Python files for AST
    if not file_pattern.endswith(".py"):
      file_pattern = "**/*.py"

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
            if node.name == pattern:
              match = True
              node_type = "function"

          elif definition_type in ("class", "any") and isinstance(node, ast.ClassDef):
            if node.name == pattern:
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

      except (SyntaxError, Exception) as e:
        logger.debug(f"Error parsing {file_path}: {e}")
        continue

  # String and regex searches
  else:
    # Compile regex if needed
    if search_type == "regex":
      try:
        regex = re.compile(pattern)
      except re.error as e:
        logger.error(f"Invalid regex pattern: {e}")
        return [{"error": f"Invalid regex pattern: {str(e)}"}]

    for file_path in git_root.rglob(file_pattern.replace("**/", "")):
      if files_searched >= max_files:
        if not results:  # Only add warning if we haven't found anything yet
          results.append({"warning": f"Stopped after searching {max_files} files"})
        break

      if not file_path.is_file():
        continue

      files_searched += 1

      try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
          match_found = False
          match_text = None

          if search_type == "string":
            if pattern in line:
              match_found = True
              match_text = pattern
          else:  # regex
            match = regex.search(line)
            if match:
              match_found = True
              match_text = match.group(0)

          if match_found:
            result = {
              "file": str(file_path.relative_to(git_root)),
              "line": line_num,
              "match": match_text,
              "full_line": line.strip(),
            }

            # Add context if requested
            if context_lines > 0:
              start = max(0, line_num - context_lines - 1)
              end = min(len(lines), line_num + context_lines)
              context = lines[start:end]
              result["context"] = "\n".join(f"{start + i + 1}: {line}" for i, line in enumerate(context))

            results.append(result)

      except (UnicodeDecodeError, PermissionError):
        # Skip binary files or files we can't read
        continue

  logger.info(f"Searched {files_searched} files, found {len(results)} matches")
  return results


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


class PatchHunk:
  """Represents a single hunk in a patch"""

  def __init__(self, old_start: int, old_count: int, new_start: int, new_count: int):
    self.old_start = old_start
    self.old_count = old_count
    self.new_start = new_start
    self.new_count = new_count
    self.raw_lines = []  # All lines in order with their types

  def get_expected_content(self) -> list[str]:
    """Get the content we expect to find in the file"""
    return [line for line_type, line in self.raw_lines if line_type in (" ", "-")]

  def get_replacement_content(self) -> list[str]:
    """Get the content to replace with"""
    return [line for line_type, line in self.raw_lines if line_type in (" ", "+")]


class ImprovedPatchParser:
  """Improved patch parser with better error handling"""

  def __init__(self, patch_content: str):
    self.patch_lines = patch_content.splitlines(keepends=True)
    self.hunks: list[PatchHunk] = []
    self._parse()

  def _parse(self):
    """Parse the patch into hunks"""
    hunk_header_re = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    current_hunk = None

    for line in self.patch_lines:
      # Skip file headers
      if line.startswith("---") or line.startswith("+++"):
        continue

      # Check for hunk header
      match = hunk_header_re.match(line)
      if match:
        # Save previous hunk
        if current_hunk:
          self.hunks.append(current_hunk)

        # Create new hunk
        old_start = int(match.group(1))
        old_count = int(match.group(2) or 1)
        new_start = int(match.group(3))
        new_count = int(match.group(4) or 1)

        current_hunk = PatchHunk(old_start, old_count, new_start, new_count)

      elif current_hunk and line:
        # Process hunk content
        if line.startswith("-") and len(line) > 1:
          current_hunk.raw_lines.append(("-", line[1:]))
        elif line.startswith("+") and len(line) > 1:
          current_hunk.raw_lines.append(("+", line[1:]))
        elif line.startswith(" "):
          current_hunk.raw_lines.append((" ", line[1:]))

    # Don't forget the last hunk
    if current_hunk:
      self.hunks.append(current_hunk)


class ContextMatcher:
  """Sophisticated context matching with fuzzy logic"""

  def __init__(self, tolerance: float = 0.85):
    self.tolerance = tolerance

  def find_best_match(self, expected_lines: list[str], file_lines: list[str], start_hint: int) -> int | None:
    """Find the best matching position for expected content"""
    # First try exact match at expected position
    if self._try_exact_match(expected_lines, file_lines, start_hint):
      return start_hint

    # Try searching nearby (± 10 lines)
    search_range = 10
    for offset in range(1, search_range + 1):
      # Try forward
      if start_hint + offset < len(file_lines):
        if self._try_exact_match(expected_lines, file_lines, start_hint + offset):
          logger.info(f"Found exact match {offset} lines forward")
          return start_hint + offset

      # Try backward
      if start_hint - offset >= 0:
        if self._try_exact_match(expected_lines, file_lines, start_hint - offset):
          logger.info(f"Found exact match {offset} lines backward")
          return start_hint - offset

    # Fall back to fuzzy matching
    best_pos, best_score = self._fuzzy_search(expected_lines, file_lines, start_hint)
    if best_score >= self.tolerance:
      logger.info(f"Found fuzzy match at line {best_pos + 1} with score {best_score:.2f}")
      return best_pos

    return None

  def _try_exact_match(self, expected: list[str], file_lines: list[str], start: int) -> bool:
    """Check if expected lines exactly match at given position"""
    if start < 0 or start + len(expected) > len(file_lines):
      return False

    for i, expected_line in enumerate(expected):
      if self._normalize_line(expected_line) != self._normalize_line(file_lines[start + i]):
        return False

    return True

  def _fuzzy_search(self, expected: list[str], file_lines: list[str], hint: int) -> tuple[int, float]:
    """Search for best fuzzy match near hint position"""
    best_pos = hint - 1
    best_score = 0.0

    # Search window based on file size
    window = min(50, len(file_lines) // 10)
    start = max(0, hint - window)
    end = min(len(file_lines) - len(expected) + 1, hint + window)

    for pos in range(start, end):
      score = self._calculate_similarity(expected, file_lines[pos : pos + len(expected)])
      if score > best_score:
        best_score = score
        best_pos = pos

    return best_pos, best_score

  def _calculate_similarity(self, expected: list[str], actual: list[str]) -> float:
    """Calculate similarity score between line sequences"""
    if len(expected) != len(actual):
      return 0.0

    scores = []
    for exp_line, act_line in zip(expected, actual):
      # Normalize and compare
      exp_norm = self._normalize_line(exp_line)
      act_norm = self._normalize_line(act_line)

      matcher = difflib.SequenceMatcher(None, exp_norm, act_norm)
      scores.append(matcher.ratio())

    return sum(scores) / len(scores) if scores else 0.0

  def _normalize_line(self, line: str) -> str:
    """Normalize line for comparison"""
    # Strip trailing whitespace but preserve indentation
    return line.rstrip()


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
    # Parse the patch
    parser = ImprovedPatchParser(patch)
    if not parser.hunks:
      return {"status": "error", "error": "No valid hunks found in patch"}

    # Validate and resolve path
    target_path = get_safe_path(file_path, must_exist=True)

    # Create backup first
    backup_name = f".{target_path.name}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    backup_path = target_path.parent / backup_name
    backup_path.write_bytes(target_path.read_bytes())

    # Read current content
    original_content = target_path.read_text()
    working_lines = original_content.splitlines(keepends=True)

    # Apply hunks with sophisticated matching
    matcher = ContextMatcher()
    applied_hunks = 0
    offset = 0  # Track cumulative line offset

    # Sort hunks by line number to apply in order
    sorted_hunks = sorted(parser.hunks, key=lambda h: h.old_start)

    for hunk in sorted_hunks:
      # Adjust for previous modifications
      adjusted_start = hunk.old_start - 1 + offset

      # Get expected content
      expected_lines = hunk.get_expected_content()

      # Find best match position
      match_pos = matcher.find_best_match(expected_lines, working_lines, adjusted_start)

      if match_pos is None:
        error_msg = f"Failed to find context for hunk starting at line {hunk.old_start}"
        logger.error(error_msg)

        # Restore from backup
        if backup_path and backup_path.exists():
          target_path.write_text(original_content)
          logger.info("Restored from backup after error")

        return {"status": "error", "error": error_msg, "failed_hunk": hunk.old_start}

      # Apply the hunk
      replacement = hunk.get_replacement_content()

      # Ensure proper line endings
      if working_lines and replacement and not replacement[-1].endswith("\n"):
        replacement[-1] += "\n"

      # Perform replacement
      end_pos = match_pos + len(expected_lines)
      working_lines[match_pos:end_pos] = replacement

      # Update offset for next hunk
      offset += len(replacement) - len(expected_lines)
      applied_hunks += 1

      logger.info(f"Applied hunk {applied_hunks}/{len(parser.hunks)} at line {match_pos + 1}")

    # Write result
    result_content = "".join(working_lines)
    target_path.write_text(result_content)

    # Validate syntax after patching
    validation = validate_syntax(target_path)

    # Calculate total lines changed
    lines_changed = sum(
      len([l for t, l in h.raw_lines if t == "-"]) + len([l for t, l in h.raw_lines if t == "+"]) for h in parser.hunks
    )

    return {
      "status": "success",
      "backup_path": str(backup_path.relative_to(find_git_root())),
      "lines_changed": lines_changed,
      "hunks_applied": applied_hunks,
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
  _validate_parser = subparsers.add_parser("validate", help="Validate the MCP server syntax and configuration")

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
