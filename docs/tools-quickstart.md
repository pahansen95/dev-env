# MCP Project Integration Agent Quickstart Guide

## Overview

The MCP Project Integration provides a comprehensive toolkit for interacting with local development projects through Claude Desktop. All operations are bounded by Git repository limits, ensuring safe execution within project boundaries.

## Core Concepts

### Project Boundaries
All tools operate within the Git repository root. Path validation prevents operations outside the repository, protecting the broader filesystem.

### Git-Centric Design
The integration assumes operation within a Git repository. Most workflows incorporate Git state tracking for safe, reversible operations.

## Essential Tools

### 1. Establishing Context

Always start by understanding the project state:

```
project_status()
```

Returns comprehensive health information including:
- Git branch and commit status
- Python environment configuration
- Project structure overview
- Working directory cleanliness

### 2. File Operations

#### Reading Files
```
file_read("src/main.py")
file_read("README.md")
```

#### Writing Files
```
file_write("src/utils.py", "def helper():\n    pass")
```

#### Managing Structure
```
file_create_directory("src/components")
file_move("old_module.py", "src/legacy/old_module.py")
file_delete("temp/cache.json")
```

### 3. Search Operations

#### Finding Files
```
# Find all Python files
search_files("*.py", match_type="glob")

# Find test directories
search_files("test", match_type="name", target_type="dir")

# Find specific file
search_files("setup.py", match_type="exact")
```

#### Searching Content
```
# Find TODO comments
search_content("TODO", file_pattern="**/*.py")

# Find function definitions
search_content("process_data", search_type="ast")

# Find imports with regex
search_content("^import", search_type="regex")
```

### 4. Git Operations

#### Check Repository State
```
git_status()
```

#### Review Changes
```
# All unstaged changes
git_diff()

# Specific file changes
git_diff("src/main.py")

# Staged changes
git_diff(staged=True)
```

#### Commit Changes
```
# Commit all staged changes
git_commit("Add authentication module")

# Stage and commit specific files
git_commit("Update config", files=["config.py", "settings.json"])
```

## Common Workflows

### Basic Code Review and Edit

1. **Establish context**
   ```
   project_status()
   ```

2. **Find relevant files**
   ```
   search_files("auth", match_type="name")
   ```

3. **Review code**
   ```
   file_read("src/auth.py")
   ```

4. **Make changes**
   ```
   file_write("src/auth.py", updated_content)
   ```

5. **Verify and commit**
   ```
   git_diff("src/auth.py")
   git_commit("Improve authentication error handling", files=["src/auth.py"])
   ```

### Applying Code Patches

For precise code modifications using unified diff format:

```
patch_apply("src/config.py", """
--- a/config.py
+++ b/config.py
@@ -10,3 +10,3 @@
-DEBUG = False
+DEBUG = True
""")
```

The patch tool provides:
- Fuzzy matching for displaced code
- Automatic backup creation
- Syntax validation after patching
- Rollback on failure

### Project Structure Analysis

1. **Explore directory structure**
   ```
   search_files("*", target_type="dir")
   ```

2. **Find specific file types**
   ```
   search_files("*.json", match_type="glob", directory="config")
   ```

3. **Analyze code patterns**
   ```
   search_content("class", search_type="ast", definition_type="class")
   ```

## Best Practices

### 1. Always Start with Context
Begin every workflow with `project_status()` to understand the current state.

### 2. Use Progressive Discovery
- Start broad with `search_files()` 
- Narrow down with `search_content()`
- Read specific files with `file_read()`

### 3. Validate Before Committing
- Use `git_diff()` to review changes
- Check `git_status()` for unexpected modifications
- Write descriptive commit messages

### 4. Backup Before Major Changes
Create copies of critical files before extensive modifications:
```
file_copy("config.py", "config.py.backup")
```

### 5. Handle Errors Gracefully
All tools return structured error information:
```python
result = file_read("nonexistent.py")
if "error" in result:
    # Handle missing file
```

## Advanced Patterns

### Multi-File Refactoring
```
# Find all files to refactor
files = search_files("*.py", directory="src/legacy")

# Process each file
for file in files:
    content = file_read(file)
    # Transform content
    file_write(file, transformed_content)

# Commit all changes
git_commit("Refactor legacy module", files=files)
```

### Safe File Operations
```
# Create backup before major changes
file_copy("config.py", "config.py.backup")

# Make changes
file_write("config.py", new_config)

# Verify changes work
# If issues, restore from backup
file_move("config.py.backup", "config.py")
```

### Incremental Development
```
# Make small, focused changes
file_read("src/api.py")
# Modify specific function
file_write("src/api.py", updated_api)

# Test and verify
git_diff("src/api.py")

# Commit if successful
git_commit("Fix API rate limiting", files=["src/api.py"])
```

## Tool Categories Reference

### Project Management
- `project_status`: Comprehensive health check

### File Operations  
- `file_read`: Read text files
- `file_write`: Create/overwrite files
- `file_create_directory`: Create directories
- `file_move`: Move/rename items
- `file_delete`: Remove items
- `file_copy`: Duplicate items

### Search Operations
- `search_files`: Find files by pattern
- `search_content`: Search within files

### Git Operations
- `git_status`: Repository state
- `git_diff`: Show changes
- `git_commit`: Create commits
- `git_log`: View history

### Development Operations
- `patch_apply`: Apply unified diffs

### Documentation
- `tool_usage`: Get detailed help

## Getting Help

For detailed documentation on any tool:
```
tool_usage("tool_name")
```

This provides:
- Conceptual model
- Usage scenarios
- Anti-patterns
- Progressive examples
- Error handling guidance
- Performance characteristics

## Common Error Patterns

### File Not Found
```
result = file_read("missing.py")
# Returns: {"error": "File not found: missing.py"}
```

### Path Outside Repository
```
result = file_read("../../../etc/passwd")
# Returns: {"error": "Path must be within project boundaries"}
```

### Invalid Git Operation
```
result = git_commit("Empty commit")
# Returns: {"error": "No changes staged for commit"}
```

## Performance Considerations

### Search Limits
- `search_files`: Results limited to 10,000 items
- `search_content`: Default 100 files, max 1000

### Large File Handling
- Binary files automatically excluded from content search
- UTF-8 validation prevents reading binary files

### Atomic Operations
- File writes are atomic (temp file + rename)
- Patch applications create automatic backups
- Git operations maintain repository consistency

## Summary

The MCP Project Integration transforms isolated file operations into coherent development workflows. By combining Git-aware boundaries, atomic operations, and comprehensive search capabilities, agents can safely and effectively participate in software development tasks.

Start simple with basic file operations, then progress to complex workflows using patches and multi-file refactoring. Always validate changes before committing, and leverage the comprehensive documentation system when exploring new capabilities.