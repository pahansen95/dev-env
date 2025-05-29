#!/usr/bin/env bash
# Python environment setup script
# Manages pyenv, Python installation, and virtual environment creation

set -euo pipefail

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Configuration
VENV_DIR="${VENV_DIR:-.venv}"
DEFAULT_PYTHON_VERSION="3.13"

# Help text
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  -q, --quiet      Suppress informational output
  --skip-venv      Skip virtual environment creation
  --force          Force recreate virtual environment
  --no-deps        Skip dependency installation
  --sync-only      Only sync existing dependencies (no new installs)
  -h, --help       Show this help message
EOF
}

# Parse command line arguments
QUIET_MODE=false
SKIP_VENV=false
FORCE_RECREATE=false
INSTALL_DEPS=true
SYNC_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--quiet)
            QUIET_MODE=true
            HELPERS_UTILS_QUIET=true
            shift
            ;;
        --skip-venv)
            SKIP_VENV=true
            shift
            ;;
        --force)
            FORCE_RECREATE=true
            shift
            ;;
        --no-deps)
            INSTALL_DEPS=false
            shift
            ;;
        --sync-only)
            SYNC_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check dependencies
check_dependencies() {
    local missing_deps=()
    
    if ! command_exists pyenv; then
        missing_deps+=("pyenv")
    fi
    
    if ! command_exists uv; then
        missing_deps+=("uv")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        echo
        echo "Installation instructions:"
        echo "  pyenv: https://github.com/pyenv/pyenv#installation"
        echo "  uv: https://github.com/astral-sh/uv"
        return 1
    fi
    
    return 0
}

# Get project root
get_project_root_alt() {
    if git rev-parse --git-dir >/dev/null 2>&1; then
        git rev-parse --show-toplevel
    else
        log_error "Not in a git repository"
        return 1
    fi
}

# Setup Python version
setup_python_version() {
    local project_root=$1
    local python_version
    
    # Check for .python-version file
    if [ -f "$project_root/.python-version" ]; then
        python_version=$(cat "$project_root/.python-version" | tr -d '[:space:]')
        if [ -z "$python_version" ]; then
            log_error ".python-version file is empty"
            return 1
        fi
        log_info "Using Python version from .python-version: $python_version"
    else
        python_version="$DEFAULT_PYTHON_VERSION"
        log_warning "No .python-version file found, creating one with Python $python_version"
        echo "$python_version" > "$project_root/.python-version"
    fi
    
    # Check if Python version is installed
    if ! pyenv versions --bare | grep -q "^$python_version"; then
        log_info "Python $python_version not installed, searching for available version..."
        
        # Find the latest matching version
        local available=$(pyenv install --list | grep -E "^\s*$python_version" | sed 's/^[[:space:]]*//' | grep -v '[a-zA-Z]' | sort -V | tail -1)
        
        if [ -z "$available" ]; then
            log_error "No Python version matching $python_version found"
            log_info "Available versions:"
            pyenv install --list | grep -E "^\s*3\.(11|12|13)" | head -20
            return 1
        fi
        
        log_info "Installing Python $available..."
        pyenv install "$available"
        python_version="$available"
        
        # Update .python-version with actual installed version
        echo "$python_version" > "$project_root/.python-version"
    fi
    
    # Set local Python version
    cd "$project_root"
    pyenv local "$python_version"
    log_success "Python $python_version configured"
    
    echo "$python_version"
}

# Create virtual environment
create_virtual_environment() {
    local project_root=$1
    local venv_path="$project_root/$VENV_DIR"
    
    if [ "$SKIP_VENV" = true ]; then
        log_info "Skipping virtual environment creation (--skip-venv)"
        return 0
    fi
    
    if [ -d "$venv_path" ]; then
        if [ "$FORCE_RECREATE" = true ]; then
            log_info "Force recreating virtual environment..."
            rm -rf "$venv_path"
        else
            log_warning "Virtual environment already exists at $VENV_DIR"
            if [ "$QUIET_MODE" = false ]; then
                read -p "Do you want to recreate it? (y/N) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    log_info "Removing existing virtual environment..."
                    rm -rf "$venv_path"
                else
                    log_info "Keeping existing virtual environment"
                    return 0
                fi
            else
                log_info "Keeping existing virtual environment"
                return 0
            fi
        fi
    fi
    
    log_info "Creating virtual environment with uv..."
    cd "$project_root"
    uv venv --python "$(pyenv which python)" "$VENV_DIR"
    log_success "Virtual environment created at $VENV_DIR"
}

# Install dependencies
install_dependencies() {
    local project_root=$1
    
    if [ "$INSTALL_DEPS" = false ]; then
        log_info "Skipping dependency installation (--no-deps)"
        return 0
    fi
    
    # Check if pyproject.toml exists
    if [ ! -f "$project_root/pyproject.toml" ]; then
        log_warning "No pyproject.toml found, skipping dependency installation"
        return 0
    fi
    
    cd "$project_root"
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    if [ "$SYNC_ONLY" = true ]; then
        log_info "Syncing existing dependencies..."
        uv sync
    else
        # Check if we need to add dependencies to existing project
        log_info "Checking project dependencies..."
        
        # Check if core dependencies are missing
        if ! grep -q "docker" "$project_root/pyproject.toml"; then
            log_info "Installing core dependencies..."
            uv add docker pydantic click rich
        else
            log_info "Core dependencies already configured"
        fi
        
        # Check if dev dependencies need to be added
        if grep -q "\[dependency-groups\]" "$project_root/pyproject.toml" || grep -q "\[project.optional-dependencies\]" "$project_root/pyproject.toml"; then
            log_info "Installing development dependencies..."
            # Check if common dev dependencies are missing
            if ! grep -q "pytest-cov" "$project_root/pyproject.toml"; then
                uv add --group dev pytest-cov pytest-mock types-docker
            fi
        fi
        
        # Sync all dependencies
        log_info "Syncing all dependencies to virtual environment..."
        uv sync
    fi
    
    log_success "Dependencies installed successfully"
}

# Main execution
main() {
    start_timer "python_setup"
    
    if [ "$QUIET_MODE" = false ]; then
        echo
        echo "========================================"
        echo "    Python Environment Setup"
        echo "========================================"
        echo
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Get project root
    PROJECT_ROOT=$(get_project_root_alt) || exit 1
    log_info "Project root: $PROJECT_ROOT"
    
    # Setup Python version
    PYTHON_VERSION=$(setup_python_version "$PROJECT_ROOT") || exit 1
    
    # Create virtual environment
    create_virtual_environment "$PROJECT_ROOT" || exit 1
    
    # Install dependencies
    if [ "$SKIP_VENV" = false ]; then
        install_dependencies "$PROJECT_ROOT" || exit 1
    fi
    
    # Final message
    if [ "$SKIP_VENV" = false ]; then
        echo
        log_timer "python_setup"
        log_success "Python environment setup complete!"
        echo "Activate the virtual environment with:"
        echo "  source $VENV_DIR/bin/activate"
        
        if [ "$INSTALL_DEPS" = true ] && [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
            echo
            echo "Dependencies installed. Key packages:"
            uv pip list | grep -E "(docker|pydantic|click|rich|pytest|ruff|mypy)" | head -10 || true
        fi
    fi
}

# Run main function
main "$@"