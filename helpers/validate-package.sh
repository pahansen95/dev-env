#!/bin/bash
# validate-package.sh - Validate package readiness for release
# Ensures package quality before creating a release

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source utilities
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_VERSION_MISMATCH=10
readonly EXIT_UNCOMMITTED_CHANGES=11
readonly EXIT_BUILD_FAILED=12
readonly EXIT_INSTALL_FAILED=13
readonly EXIT_IMPORT_FAILED=14
readonly EXIT_CLI_FAILED=15
readonly EXIT_TAG_FAILED=16

# Configuration
readonly TEST_VENV=".test-venv"
readonly DIST_DIR="dist"
readonly INIT_FILE="src/dev_env/__init__.py"
readonly PYPROJECT_FILE="pyproject.toml"

# Parse command line arguments
TAG_MODE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag-mode)
            TAG_MODE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--tag-mode]"
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [[ -d "$TEST_VENV" ]]; then
        log_info "Cleaning up test environment"
        rm -rf "$TEST_VENV"
    fi
}

# Main validation function
main() {
    log_info "Starting package validation"
    start_timer "validation"
    
    # Change to project root
    cd "$(get_project_root)"
    
    # Check prerequisites
    log_progress "Checking prerequisites"
    require_command python3 "Install Python 3.13+" || exit $EXIT_VERSION_MISMATCH
    require_command git "Install Git" || exit $EXIT_VERSION_MISMATCH
    require_command uv "Install uv (https://docs.astral.sh/uv/)" || exit $EXIT_VERSION_MISMATCH
    
    # 1. Check version consistency
    log_progress "Checking version consistency"
    local init_version
    init_version=$(get_python_version "$INIT_FILE") || {
        log_error "Failed to extract version from $INIT_FILE"
        exit $EXIT_VERSION_MISMATCH
    }
    
    local pyproject_version
    pyproject_version=$(get_pyproject_version "$PYPROJECT_FILE") || {
        log_error "Failed to extract version from $PYPROJECT_FILE"
        exit $EXIT_VERSION_MISMATCH
    }
    
    if [[ "$init_version" != "$pyproject_version" ]]; then
        log_error "Version mismatch:"
        log_error "  $INIT_FILE: $init_version"
        log_error "  $PYPROJECT_FILE: $pyproject_version"
        exit $EXIT_VERSION_MISMATCH
    fi
    
    log_success "Version consistency check passed: $init_version"
    
    # 2. Check for uncommitted changes
    log_progress "Checking for uncommitted changes"
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_error "Uncommitted changes found. Please commit or stash changes before validation."
        git status --short
        exit $EXIT_UNCOMMITTED_CHANGES
    fi
    
    log_success "Working directory is clean"
    
    # 3. Build the package
    log_progress "Building package"
    "${SCRIPT_DIR}/build-package.sh" || {
        log_error "Package build failed"
        exit $EXIT_BUILD_FAILED
    }
    
    # 4. Test installation in fresh venv
    log_progress "Testing package installation"
    uv venv "$TEST_VENV" --python python3 || {
        log_error "Failed to create test environment"
        exit $EXIT_INSTALL_FAILED
    }
    
    # Find the wheel file
    local wheel_file
    wheel_file=$(find "$DIST_DIR" -name "*.whl" | head -n1)
    
    if [[ -z "$wheel_file" ]]; then
        log_error "No wheel file found in $DIST_DIR"
        exit $EXIT_INSTALL_FAILED
    fi
    
    # Install the wheel using uv
    uv pip install --python "$TEST_VENV/bin/python" "$wheel_file" || {
        log_error "Failed to install package"
        exit $EXIT_INSTALL_FAILED
    }
    
    log_success "Package installed successfully"
    
    # 5. Test import
    log_progress "Testing Python import"
    "$TEST_VENV/bin/python" -c "import dev_env" || {
        log_error "Failed to import dev_env module"
        exit $EXIT_IMPORT_FAILED
    }
    
    log_success "Python import test passed"
    
    # 6. Test CLI command
    log_progress "Testing CLI command"
    "$TEST_VENV/bin/dev-env" --version || {
        log_error "CLI command 'dev-env --version' failed"
        exit $EXIT_CLI_FAILED
    }
    
    log_success "CLI command test passed"
    
    # 7. Tag mode validation
    if [[ "$TAG_MODE" == "true" ]]; then
        log_progress "Performing tag validation"
        
        # Check if current commit has a tag
        local current_tag
        current_tag=$(get_current_tag)
        
        if [[ -z "$current_tag" ]]; then
            log_error "No tag found on current commit"
            exit $EXIT_TAG_FAILED
        fi
        
        # Validate tag format
        if ! is_valid_semver "$current_tag"; then
            log_error "Tag '$current_tag' is not a valid semver format (expected: vX.Y.Z)"
            exit $EXIT_TAG_FAILED
        fi
        
        # Check if tag matches package version
        local expected_tag="v${init_version}"
        if [[ "$current_tag" != "$expected_tag" ]]; then
            log_error "Tag mismatch:"
            log_error "  Current tag: $current_tag"
            log_error "  Expected tag: $expected_tag (based on package version)"
            exit $EXIT_TAG_FAILED
        fi
        
        log_success "Tag validation passed: $current_tag"
    fi
    
    # Cleanup
    cleanup
    
    log_timer "validation"
    log_success "All validation checks passed!"
    
    if [[ "$TAG_MODE" != "true" ]]; then
        log_info "Ready to create release tag: v${init_version}"
        log_info "To create tag: git tag v${init_version} && git push origin v${init_version}"
    fi
    
    exit $EXIT_SUCCESS
}

# Set cleanup trap
trap cleanup EXIT

# Run main function
main "$@"