#!/usr/bin/env bash
# Comprehensive project setup script for dev-env
# Sets up Python environment with pyenv & uv, installs dependencies

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv"
PYTHON_VERSION="3.12"  # Default if .python-version doesn't exist
MIN_PYTHON_VERSION="3.11"

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo
echo "========================================"
echo "    dev-env Project Setup Script"
echo "========================================"
echo

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

# Step 1: Check dependencies
log_info "Checking system dependencies..."

missing_deps=()

if ! command -v pyenv >/dev/null 2>&1; then
    missing_deps+=("pyenv")
fi

if ! command -v uv >/dev/null 2>&1; then
    missing_deps+=("uv")
fi

if [ ${#missing_deps[@]} -ne 0 ]; then
    log_error "Missing required dependencies: ${missing_deps[*]}"
    echo
    echo "Installation instructions:"
    echo "  pyenv: https://github.com/pyenv/pyenv#installation"
    echo "  uv: https://github.com/astral-sh/uv"
    exit 1
fi

log_success "All system dependencies found"

# Step 2: Setup Python version
log_info "Setting up Python environment..."

# Check for .python-version file
if [ -f "$PROJECT_ROOT/.python-version" ]; then
    PYTHON_VERSION=$(cat "$PROJECT_ROOT/.python-version" | tr -d '[:space:]')
    log_info "Using Python version from .python-version: $PYTHON_VERSION"
else
    log_warning "No .python-version file found, creating one with Python $PYTHON_VERSION"
    echo "$PYTHON_VERSION" > "$PROJECT_ROOT/.python-version"
fi

# Check if Python version is installed
if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION"; then
    log_info "Python $PYTHON_VERSION not installed, searching for available version..."
    
    # Find the latest matching version
    AVAILABLE=$(pyenv install --list | grep -E "^\s*$PYTHON_VERSION" | sed 's/^[[:space:]]*//' | grep -v '[a-zA-Z]' | sort -V | tail -1)
    
    if [ -z "$AVAILABLE" ]; then
        log_error "No Python version matching $PYTHON_VERSION found"
        log_info "Available versions:"
        pyenv install --list | grep -E "^\s*3\.(11|12)" | head -20
        exit 1
    fi
    
    log_info "Installing Python $AVAILABLE..."
    pyenv install "$AVAILABLE"
    PYTHON_VERSION="$AVAILABLE"
    
    # Update .python-version with actual installed version
    echo "$PYTHON_VERSION" > "$PROJECT_ROOT/.python-version"
fi

# Set local Python version
pyenv local "$PYTHON_VERSION"
log_success "Python $PYTHON_VERSION configured"

# Step 3: Create virtual environment
log_info "Setting up virtual environment..."

if [ -d "$PROJECT_ROOT/$VENV_DIR" ]; then
    log_warning "Virtual environment already exists at $VENV_DIR"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Removing existing virtual environment..."
        rm -rf "$PROJECT_ROOT/$VENV_DIR"
    else
        log_info "Keeping existing virtual environment"
    fi
fi

if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
    log_info "Creating virtual environment with uv..."
    uv venv --python "$(pyenv which python)" "$VENV_DIR"
    log_success "Virtual environment created"
fi

# Step 4: Activate virtual environment
log_info "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Step 5: Setup project dependencies
log_info "Setting up project dependencies..."

# Check if we need to add dependencies to existing project
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
    log_info "Found existing pyproject.toml"
    
    # Check if core dependencies are missing
    if ! grep -q "docker" "$PROJECT_ROOT/pyproject.toml"; then
        log_info "Installing core dependencies..."
        uv add docker pydantic click rich
    else
        log_info "Core dependencies already configured"
    fi
    
    # Check if dev dependencies need updates
    log_info "Ensuring development dependencies are installed..."
    uv add --group dev pytest-cov pytest-mock types-docker
    
else
    log_warning "No pyproject.toml found, initializing project with uv..."
    
    # Initialize the project with uv
    uv init --name "dev-env" --no-readme --python "$PYTHON_VERSION"
    
    # Install core dependencies
    log_info "Installing core dependencies..."
    uv add docker pydantic click rich
    
    # Install development dependencies
    log_info "Installing development dependencies..."
    uv add --group dev mypy pytest pytest-cov pytest-mock ruff pre-commit types-docker
fi

# Sync dependencies to virtual environment
log_info "Syncing dependencies to virtual environment..."
uv sync

# Step 6: Create project structure
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

# Step 7: Setup git hooks (optional)
log_info "Setting up git hooks..."

# Create pre-commit hook for style enforcement
HOOK_FILE="$PROJECT_ROOT/.git/hooks/pre-commit"
if [ ! -f "$HOOK_FILE" ]; then
    cat > "$HOOK_FILE" << 'EOF'
#!/usr/bin/env bash
# Pre-commit hook to enforce style

# Run style enforcement on staged Python files
staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')

if [ -n "$staged_files" ]; then
    echo "Running style enforcement on staged Python files..."
    if ./helpers/enforce-style.sh $staged_files; then
        # Re-stage files that were modified by formatting
        for file in $staged_files; do
            if [ -f "$file" ]; then
                git add "$file"
            fi
        done
    else
        echo "Style enforcement failed. Please fix issues and try again."
        exit 1
    fi
fi
EOF
    chmod +x "$HOOK_FILE"
    log_success "Created pre-commit hook"
else
    log_info "Pre-commit hook already exists"
fi

# Step 8: Final checks
log_info "Running final checks..."

# Verify Python version
ACTUAL_PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
log_info "Python version: $ACTUAL_PYTHON_VERSION"

# List installed packages
log_info "Key packages installed:"
uv pip list | grep -E "(docker|pydantic|click|rich|pytest|ruff|mypy)" || true

echo
echo "========================================"
log_success "Project setup complete!"
echo "========================================"
echo
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source $VENV_DIR/bin/activate"
echo
echo "2. Run style enforcement:"
echo "   ./helpers/enforce-style.sh"
echo
echo "3. Start developing!"
echo "   - Source code goes in: src/dev_env/"
echo "   - Tests go in: tests/"
echo "   - Examples go in: examples/"
echo "   - Mental models go in: models/"
echo
echo "Development commands:"
echo "  ruff check .     # Run linter"
echo "  ruff format .    # Format code"
echo "  mypy .           # Type checking"
echo "  pytest           # Run tests"
echo
echo "Note: Docker SDK is installed for remote Docker support."
echo "Set DOCKER_HOST environment variable to connect to remote Docker."
echo