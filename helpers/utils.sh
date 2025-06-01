#!/bin/bash
# utils.sh - Shared utilities for helper scripts (simplified for compatibility)
# Source this file to use common functions across helper scripts

# Prevent double-sourcing
if [[ -n "${HELPERS_UTILS_LOADED:-}" ]]; then
    return 0
fi
HELPERS_UTILS_LOADED=1

# Default configuration
HELPERS_UTILS_VERSION="1.0.0"
HELPERS_UTILS_VERBOSE="${VERBOSE:-false}"
HELPERS_UTILS_QUIET="${QUIET:-false}"

# Colors for output (can be disabled by setting NO_COLOR=1)
if [[ -z "${NO_COLOR:-}" ]] && [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[1;33m'
    readonly BLUE='\033[0;34m'
    readonly PURPLE='\033[0;35m'
    readonly CYAN='\033[0;36m'
    readonly NC='\033[0m' # No Color
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly PURPLE=''
    readonly CYAN=''
    readonly NC=''
fi

# Logging functions
log_info() {
    if [[ "$HELPERS_UTILS_QUIET" != "true" ]]; then
        echo -e "${BLUE}[INFO]${NC} $1" >&2
    fi
}

log_success() {
    if [[ "$HELPERS_UTILS_QUIET" != "true" ]]; then
        echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
    fi
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_debug() {
    if [[ "$HELPERS_UTILS_VERBOSE" == "true" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1" >&2
    fi
}

# Progress indicator
log_progress() {
    if [[ "$HELPERS_UTILS_QUIET" != "true" ]]; then
        echo -e "${CYAN}[PROGRESS]${NC} $1" >&2
    fi
}

# Utility functions
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get script directory (works when sourced)
get_script_dir() {
    local source="${BASH_SOURCE[1]}"
    while [[ -L "$source" ]]; do
        local dir="$(cd -P "$(dirname "$source")" && pwd)"
        source="$(readlink "$source")"
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# Get project root (assumes helpers/ is one level down from project root)
get_project_root() {
    local script_dir="$(get_script_dir)"
    cd "$(dirname "$script_dir")" && pwd
}

# Validate required environment
require_command() {
    local cmd="$1"
    local install_hint="${2:-}"
    
    if ! command_exists "$cmd"; then
        log_error "Required command '$cmd' not found"
        if [[ -n "$install_hint" ]]; then
            log_info "Install with: $install_hint"
        fi
        return 1
    fi
}

# Validate directory exists
require_directory() {
    local dir="$1"
    local description="${2:-directory}"
    
    if [[ ! -d "$dir" ]]; then
        log_error "Required $description not found: $dir"
        return 1
    fi
}

# Simple argument parsing using positional parameters and flags
# For more complex parsing, scripts can handle their own argument parsing

# Environment setup utilities
setup_python_venv() {
    local venv_path="$1"
    local requirements_file="${2:-}"
    
    log_info "Setting up Python virtual environment at $venv_path"
    
    if [[ ! -d "$venv_path" ]]; then
        log_info "Creating virtual environment..."
        python3 -m venv "$venv_path" || {
            log_error "Failed to create virtual environment"
            return 1
        }
    fi
    
    # Activate virtual environment
    # shellcheck source=/dev/null
    source "$venv_path/bin/activate" || {
        log_error "Failed to activate virtual environment"
        return 1
    }
    
    log_info "Using Python $(python --version 2>&1 | cut -d' ' -f2)"
    
    # Install requirements if provided
    if [[ -n "$requirements_file" ]] && [[ -f "$requirements_file" ]]; then
        log_info "Installing requirements from $requirements_file"
        pip install -r "$requirements_file" || {
            log_error "Failed to install requirements"
            return 1
        }
    fi
    
    log_success "Python environment ready"
}

# Cleanup utilities
cleanup_files() {
    local patterns=("$@")
    
    log_info "Cleaning up files..."
    
    for pattern in "${patterns[@]}"; do
        if [[ "$pattern" == *"/"* ]]; then
            # Directory pattern
            find . -type d -name "$(basename "$pattern")" -exec rm -rf {} + 2>/dev/null || true
        else
            # File pattern
            find . -type f -name "$pattern" -delete 2>/dev/null || true
        fi
    done
    
    log_success "Cleanup complete"
}

# Exit handling
set_exit_handler() {
    local handler_function="$1"
    trap "$handler_function" EXIT
}

# Performance timing (using global variables for compatibility)
start_timer() {
    local name="$1"
    eval "TIMER_${name}=$(date +%s)"
}

end_timer() {
    local name="$1"
    local start_var="TIMER_${name}"
    local start_time="${!start_var:-}"
    
    if [[ -n "$start_time" ]]; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo $duration
    else
        echo 0
    fi
}

log_timer() {
    local name="$1"
    local duration=$(end_timer "$name")
    log_info "$name completed in ${duration}s"
}

# Export functions for use in other scripts
# Version extraction utilities
# Extract version from Python __init__.py file
get_python_version() {
    local file="$1"
    
    if [[ ! -f "$file" ]]; then
        log_error "Python file not found: $file"
        return 1
    fi
    
    # Extract __version__ = "x.y.z" or __version__ = 'x.y.z'
    local version=$(grep -E "^__version__\s*=\s*['\"]" "$file" | sed -E 's/^__version__[[:space:]]*=[[:space:]]*["'\'']([^"'\'']+)["'\''].*/\1/')
    
    if [[ -z "$version" ]]; then
        log_error "No version found in $file"
        return 1
    fi
    
    echo "$version"
}

# Extract version from pyproject.toml
get_pyproject_version() {
    local file="${1:-pyproject.toml}"
    
    if [[ ! -f "$file" ]]; then
        log_error "pyproject.toml not found: $file"
        return 1
    fi
    
    # Extract version = "x.y.z" from [project] section
    local version=$(grep -A 20 '^\[project\]' "$file" | grep '^version[[:space:]]*=' | head -1 | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')
    
    if [[ -z "$version" ]]; then
        log_error "No version found in $file"
        return 1
    fi
    
    echo "$version"
}

# Check if current commit has a tag
get_current_tag() {
    # Get the tag pointing to current commit
    local tag=$(git describe --exact-match --tags HEAD 2>/dev/null || true)
    echo "$tag"
}

# Validate semver format
is_valid_semver() {
    local version="$1"
    
    # Check format: vX.Y.Z where X, Y, Z are numbers
    if [[ "$version" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 0
    else
        return 1
    fi
}

# Calculate SHA256 checksum using Python
calculate_checksum() {
    local file="$1"
    
    if [[ ! -f "$file" ]]; then
        log_error "File not found for checksum: $file"
        return 1
    fi
    
    # Use Python to calculate SHA256
    python3 -c "
import hashlib
import sys
with open('$file', 'rb') as f:
    hash_obj = hashlib.sha256()
    while chunk := f.read(8192):
        hash_obj.update(chunk)
    print(hash_obj.hexdigest())
" || {
        log_error "Failed to calculate checksum for $file"
        return 1
    }
}

export -f log_info log_success log_warning log_error log_debug log_progress
export -f command_exists get_script_dir get_project_root require_command require_directory
export -f setup_python_venv cleanup_files set_exit_handler
export -f start_timer end_timer log_timer
export -f get_python_version get_pyproject_version get_current_tag is_valid_semver calculate_checksum

# Set default verbosity based on imported values
if [[ "${VERBOSE:-false}" == "true" ]]; then
    HELPERS_UTILS_VERBOSE=true
fi

if [[ "${QUIET:-false}" == "true" ]]; then
    HELPERS_UTILS_QUIET=true
fi

log_debug "helpers/utils.sh v${HELPERS_UTILS_VERSION} loaded"