#!/usr/bin/env bash
# Comprehensive project setup script for dev-env
# Sets up Python environment with pyenv & uv, installs dependencies

set -euo pipefail

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Configuration
VENV_DIR=".venv"

# Banner
echo
echo "========================================"
echo "    dev-env Project Setup Script"
echo "========================================"
echo

start_timer "project_setup"

# Check if we're in a git repository
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_error "Not in a git repository. Please run from within the dev-env project."
    exit 1
fi

# Get project root
PROJECT_ROOT=$(git rev-parse --show-toplevel)
log_info "Project root: $PROJECT_ROOT"

# Change to project root
cd "$PROJECT_ROOT"

# Step 1: Setup Python environment
log_info "Setting up Python environment..."

# Call setup-python.sh
if ! "$SCRIPT_DIR/setup-python.sh"; then
    log_error "Python environment setup failed"
    exit 1
fi

log_success "Python environment setup complete"

# Step 2: Activate virtual environment
log_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Step 3: Setup project structure if needed
log_info "Checking project configuration..."

# Initialize project if pyproject.toml doesn't exist
if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
    log_warning "No pyproject.toml found, initializing project with uv..."
    
    # Get Python version from .python-version
    PYTHON_VERSION=$(cat "$PROJECT_ROOT/.python-version" | tr -d '[:space:]')
    
    # Initialize the project with uv
    uv init --name "dev-env" --no-readme --python "$PYTHON_VERSION"
    
    # Install all dependencies
    log_info "Installing project dependencies..."
    uv add docker pydantic click rich
    uv add --group dev mypy pytest pytest-cov pytest-mock ruff pre-commit types-docker
else
    log_info "Project already initialized with pyproject.toml"
fi

# Step 4: Create project structure
log_info "Setting up project structure..."

# Create necessary directories
directories=(
    "src/dev_env"
    "tests"
    "examples"
    "models"
    "docs"
)

for dir in "${directories[@]}"; do
    if [ ! -d "$PROJECT_ROOT/$dir" ]; then
        mkdir -p "$PROJECT_ROOT/$dir"
        log_info "Created directory: $dir"
    fi
    
    # Create .gitkeep for empty directories (except Python package dirs)
    # Check both new and existing directories
    if [[ "$dir" != "src/dev_env" ]] && [[ "$dir" != "tests" ]]; then
        if [ ! -f "$PROJECT_ROOT/$dir/.gitkeep" ]; then
            touch "$PROJECT_ROOT/$dir/.gitkeep"
            log_info "Created .gitkeep in: $dir"
        fi
    fi
done

# Create __init__.py files
init_files=(
    "src/dev_env/__init__.py"
    "tests/__init__.py"
)

for file in "${init_files[@]}"; do
    if [ ! -f "$PROJECT_ROOT/$file" ]; then
        touch "$PROJECT_ROOT/$file"
        log_info "Created: $file"
    fi
done

# Step 5: Setup pre-commit hooks
log_info "Setting up pre-commit hooks..."

# Check if .pre-commit-config.yaml exists
if [ -f "$PROJECT_ROOT/.pre-commit-config.yaml" ]; then
    log_info "Found existing .pre-commit-config.yaml"
else
    log_error "No .pre-commit-config.yaml found. Please create one before running setup."
    exit 1
fi

# Install pre-commit hooks
log_info "Installing pre-commit hooks..."
if pre-commit install; then
    log_success "Pre-commit hooks installed successfully"
else
    log_error "Failed to install pre-commit hooks"
    exit 1
fi

# Run pre-commit on all files to ensure everything is set up correctly
log_info "Running pre-commit on all files for initial validation..."
if pre-commit run --all-files; then
    log_success "All pre-commit checks passed"
else
    log_warning "Some pre-commit checks failed. This is normal for initial setup."
    log_info "Run 'pre-commit run --all-files' to see details"
fi

# Step 6: Final checks
log_info "Running final checks..."

# Verify Python version
ACTUAL_PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
log_info "Python version: $ACTUAL_PYTHON_VERSION"

# List installed packages
log_info "Key packages installed:"
uv pip list | grep -E "(docker|pydantic|click|rich|pytest|ruff|mypy)" || true

echo
echo "========================================"
log_timer "project_setup"
log_success "Project setup complete!"
echo "========================================"
echo
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source $VENV_DIR/bin/activate"
echo
echo "2. Run pre-commit checks:"
echo "   pre-commit run --all-files"
echo
echo "3. Start developing!"
echo "   - Source code goes in: src/dev_env/"
echo "   - Tests go in: tests/"
echo "   - Examples go in: examples/"
echo "   - Mental models go in: models/"
echo
echo "Development commands:"
echo "  pre-commit run --all-files  # Run all checks"
echo "  ruff check .                # Run linter only"
echo "  ruff format .               # Format code only"
echo "  mypy .                      # Type checking only"
echo "  pytest                      # Run tests"
echo
echo "Note: Docker SDK is installed for remote Docker support."
echo "Set DOCKER_HOST environment variable to connect to remote Docker."
echo