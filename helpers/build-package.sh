#!/bin/bash
# build-package.sh - Build Python wheel and source distribution packages
# Creates distributable packages for the dev-env project

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source utilities
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_NO_PYTHON_GIT=1
readonly EXIT_BUILD_ENV_FAILED=2
readonly EXIT_BUILD_FAILED=3

# Configuration
readonly DIST_DIR="dist"
readonly BUILD_DIR="build"
readonly CHECKSUMS_FILE="${DIST_DIR}/checksums.txt"

# Main build function
main() {
    log_info "Starting package build process"
    start_timer "build"
    
    # Change to project root
    cd "$(get_project_root)"
    
    # Check prerequisites
    log_progress "Checking prerequisites"
    require_command python3 "Install Python 3.13+" || exit $EXIT_NO_PYTHON_GIT
    require_command git "Install Git" || exit $EXIT_NO_PYTHON_GIT
    require_command uv "Install uv (https://docs.astral.sh/uv/)" || exit $EXIT_NO_PYTHON_GIT
    
    # Clean previous build artifacts
    log_progress "Cleaning previous build artifacts"
    if [[ -d "$DIST_DIR" ]]; then
        rm -rf "$DIST_DIR"
    fi
    if [[ -d "$BUILD_DIR" ]]; then
        rm -rf "$BUILD_DIR"
    fi
    # Remove any .egg-info directories
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    
    # Build the package using uv
    log_progress "Building package using uv"
    uv run --group build python -m build || {
        log_error "Package build failed"
        exit $EXIT_BUILD_FAILED
    }
    
    # Generate checksums
    log_progress "Generating checksums"
    mkdir -p "$DIST_DIR"
    : > "$CHECKSUMS_FILE"  # Create empty file
    
    for file in "${DIST_DIR}"/*.{whl,tar.gz}; do
        if [[ -f "$file" ]]; then
            local filename=$(basename "$file")
            local checksum=$(calculate_checksum "$file")
            echo "${checksum}  ${filename}" >> "$CHECKSUMS_FILE"
        fi
    done
    
    # Display package contents summary
    log_info "Package contents:"
    if command_exists tree; then
        tree "$DIST_DIR"
    else
        ls -la "$DIST_DIR"
    fi
    
    # Show checksums
    if [[ -f "$CHECKSUMS_FILE" ]]; then
        log_info "SHA256 checksums:"
        cat "$CHECKSUMS_FILE"
    fi
    
    log_timer "build"
    log_success "Package build completed successfully"
    
    # List generated files
    log_info "Generated packages:"
    for file in "${DIST_DIR}"/*.{whl,tar.gz}; do
        if [[ -f "$file" ]]; then
            echo "  - $(basename "$file")"
        fi
    done
    
    exit $EXIT_SUCCESS
}

# Run main function
main "$@"