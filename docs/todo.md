# Build & Release System Implementation Plan

## Overview

This plan describes implementing a build and release system for the dev-env project. The system consists of shell scripts that build Python packages and validate releases through git tags.

## System Architecture

The build system provides two primary functions:
- **Package Building**: Creates distributable Python packages (wheel and source)
- **Release Validation**: Ensures package quality before git tag creation

Releases occur through git tags only. No package publishing to PyPI is required.

## Prerequisites

- Python 3.13+ installed
- Git repository with existing helpers/utils.sh
- Project structure with pyproject.toml and src/dev_env/__init__.py
- Basic shell scripting knowledge

## Implementation Tasks

### Task 1: Create Build Script

**File**: `helpers/build-package.sh`

**Purpose**: Build Python wheel and source distribution packages

**Requirements**:
1. Source helpers/utils.sh for common functions
2. Create isolated build environment using Python venv
3. Install only official build tools: `pip install build`
4. Clean previous build artifacts (dist/, build/, *.egg-info)
5. Execute `python -m build` to create packages
6. Generate SHA256 checksums for artifacts
7. Display package contents summary

**Acceptance Criteria**:
- Script runs without external dependencies
- Creates both .whl and .tar.gz in dist/
- Generates dist/checksums.txt with SHA256 hashes
- Exits with code 0 on success, non-zero on failure
- Provides clear progress messages using log functions

**Exit Codes**:
- 0: Success
- 1: Python/git not available
- 2: Build environment setup failed
- 3: Package build failed

### Task 2: Create Validation Script

**File**: `helpers/validate-package.sh`

**Purpose**: Validate package readiness for release

**Requirements**:
1. Source helpers/utils.sh for common functions
2. Support two modes:
   - Standard mode: Basic package validation
   - Tag mode (--tag-mode flag): Additional git tag checks
3. Perform validation checks:
   - Version consistency between __init__.py and pyproject.toml
   - No uncommitted git changes
   - Package builds successfully (calls build-package.sh)
   - Test installation in fresh venv
   - CLI command `dev-env --version` works
   - Python import test: `python -c "import dev_env"`
4. In tag mode, additionally verify:
   - Current commit has semver tag (v*.*.*)
   - Tag matches package version

**Acceptance Criteria**:
- Validates all aspects without manual intervention
- Clear error messages indicating what failed
- Cleans up test environments after validation
- Returns appropriate exit codes for each failure type

**Exit Codes**:
- 0: All validations passed
- 10: Version mismatch
- 11: Uncommitted changes
- 12: Build failed
- 13: Installation failed
- 14: Import failed
- 15: CLI test failed
- 16: Tag validation failed

### Task 3: Extend Utilities

**File**: `helpers/utils.sh` (additions)

**New Functions Required**:

```bash
# Extract version from Python file
get_python_version() {
    local file="$1"
    # Extract __version__ = "x.y.z"
}

# Extract version from pyproject.toml
get_pyproject_version() {
    # Extract version = "x.y.z"
}

# Check if current commit has tag
get_current_tag() {
    # Return tag if exists, empty otherwise
}

# Validate semver format
is_valid_semver() {
    local version="$1"
    # Check format: vX.Y.Z
}

# Calculate SHA256 checksum
calculate_checksum() {
    local file="$1"
    # Use Python: python -c "import hashlib..."
}
```

### Task 4: Configure Pre-commit Hook

**File**: `.pre-commit-config.yaml` (modify existing)

**Addition Required**:
```yaml
  - id: validate-release
    name: Validate release package
    entry: ./helpers/validate-package.sh
    language: script
    pass_filenames: false
    stages: [manual]
    verbose: true
```

**Git Hook Setup**:
Create `.git/hooks/pre-push` to run validation on tag pushes:
```bash
#!/bin/bash
# Check if pushing a semver tag
# If yes, run validation in tag mode
```

### Task 5: Create Make Targets (Optional)

**File**: `Makefile` (create if desired)

```makefile
.PHONY: build validate release

build:
	./helpers/build-package.sh

validate:
	./helpers/validate-package.sh

release:
	@echo "To release: git tag vX.Y.Z && git push origin vX.Y.Z"
```

## Testing Procedures

### Test Build Script
1. Run `./helpers/build-package.sh`
2. Verify dist/ contains .whl and .tar.gz files
3. Verify checksums.txt exists and is accurate
4. Run again and verify cleanup works

### Test Validation Script
1. Create intentional version mismatch and verify detection
2. Add uncommitted changes and verify detection
3. Run with clean working directory and verify success
4. Test tag mode with and without valid tags

### Integration Test
1. Make code change
2. Update version in __init__.py
3. Commit changes
4. Run validation script
5. Create git tag
6. Verify pre-commit hook runs

## Implementation Order

1. Extend utils.sh with new functions (30 minutes)
2. Implement build-package.sh (45 minutes)
3. Implement validate-package.sh (60 minutes)
4. Configure pre-commit hooks (15 minutes)
5. Test all components (30 minutes)

Total estimated time: 3 hours

## Success Criteria

The implementation is complete when:
- Developers can run `./helpers/build-package.sh` to create packages
- Running `./helpers/validate-package.sh` catches all quality issues
- Git tags trigger automatic validation
- No external dependencies beyond Python standard tools
- All scripts follow existing project patterns from utils.sh

## Notes for Implementers

- Use existing logging functions from utils.sh (log_info, log_error, etc.)
- Follow existing script patterns for consistency
- Test on both Linux and macOS if possible
- Keep scripts simple and focused on single responsibility
- Document any assumptions in script comments