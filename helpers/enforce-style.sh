#!/usr/bin/env bash
# Apply ruff formatting and linting to Python files in the project
# Matches the style guidelines from helpers/apply-style.py

set -euo pipefail

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Get the project root using git
PROJECT_ROOT="$(get_project_root)" || {
    log_error "Not in a git repository"
    exit 1
}

# Default targets
DEFAULT_TARGETS=("src" "tests" "examples" "helpers")

# Help text
show_help() {
    cat << EOF
Usage: $0 [FILES_OR_DIRECTORIES...]

Apply ruff formatting and linting to Python files in the project.

Arguments:
  FILES_OR_DIRECTORIES  Files or directories to process (default: src tests examples helpers)

Options:
  -h, --help           Show this help message

Examples:
  $0                   Process default directories (src, tests, examples, helpers)
  $0 src/dev_env       Process only the src/dev_env directory
  $0 file.py           Process a specific file
EOF
}

# Parse command line arguments
if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    show_help
    exit 0
fi

if [ $# -eq 0 ]; then
    ARGS=("${DEFAULT_TARGETS[@]}")
else
    ARGS=("$@")
fi

start_timer "style_enforcement"

log_info "Project root: $PROJECT_ROOT"
log_info "Processing: ${ARGS[*]}"

# Check if ruff is available
if ! require_command "ruff" "pip install ruff"; then
    exit 1
fi

# Create a temporary directory for symlinks
TEMP_DIR=$(mktemp -d)
set_exit_handler "rm -rf $TEMP_DIR"

log_debug "Creating symlinks in temporary directory: $TEMP_DIR"

# Process arguments - can be mix of files and directories
file_count=0

for arg in "${ARGS[@]}"; do
    # Convert to absolute path if relative
    if [[ "$arg" = /* ]]; then
        path="$arg"
    else
        path="$PROJECT_ROOT/$arg"
    fi
    
    if [ ! -e "$path" ]; then
        log_warning "Skipping $arg - not found"
        continue
    fi
    
    if [ -f "$path" ]; then
        # It's a file - add it directly (no filtering)
        # Get relative path from project root
        rel_path="${path#$PROJECT_ROOT/}"
        
        # Create directory structure in temp dir
        link_dir="$TEMP_DIR/$(dirname "$rel_path")"
        mkdir -p "$link_dir"
        
        # Create symlink
        ln -s "$path" "$link_dir/$(basename "$path")"
        file_count=$((file_count + 1))
    elif [ -d "$path" ]; then
        # It's a directory - find Python files
        find "$path" -name "*.py" -type f ! -path "*/.*" -exec sh -c '
            file="$1"
            project_root="$2"
            temp_dir="$3"
            
            # Get relative path from project root
            rel_path="${file#$project_root/}"
            
            # Create directory structure in temp dir
            link_dir="$temp_dir/$(dirname "$rel_path")"
            mkdir -p "$link_dir"
            
            # Create symlink
            ln -s "$file" "$link_dir/$(basename "$file")"
        ' sh {} "$PROJECT_ROOT" "$TEMP_DIR" \;
        
        # Count the files we just linked
        dir_count=$(find "$path" -name "*.py" -type f ! -path "*/.*" | wc -l)
        file_count=$((file_count + dir_count))
    fi
done

if [ $file_count -eq 0 ]; then
    log_warning "No Python files found in specified targets"
    exit 0
fi

log_info "Found $file_count Python files"

# Run ruff check with --fix on the entire temp directory
log_info "Checking and fixing all files with ruff..."
if ruff check --fix --verbose "$TEMP_DIR"; then
    log_success "Linting complete"
    lint_success=true
else
    log_warning "Some linting issues remain (manual fixes needed)"
    # Show remaining issues
    echo
    echo "Remaining issues:"
    ruff check "$TEMP_DIR" || true
    lint_success=false
fi

echo

# Run ruff format on the entire temp directory
log_info "Formatting all files with ruff..."
if ruff format --verbose "$TEMP_DIR"; then
    log_success "Formatting complete"
    format_success=true
else
    log_error "Formatting failed"
    format_success=false
fi

echo
echo "================================"

# Final exit status
if [ "$format_success" = true ] && [ "$lint_success" = true ]; then
    log_timer "style_enforcement"
    log_success "Style enforcement complete!"
    log_info "Successfully processed $file_count files"
    exit 0
elif [ "$format_success" = false ]; then
    log_timer "style_enforcement"
    log_error "Formatting failed"
    log_info "Failed to process $file_count files"
    exit 1
else
    log_timer "style_enforcement"
    log_warning "Style enforcement complete with remaining lint issues"
    log_info "Processed $file_count files (manual fixes needed for some lint issues)"
    exit 0
fi