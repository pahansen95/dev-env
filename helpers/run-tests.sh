#!/bin/bash
set -euo pipefail

# run_tests.sh - Comprehensive test runner for dev-env project
# Can be used locally or in CI/CD pipelines

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Configuration
PROJECT_ROOT="$(get_project_root)"
VENV_PATH="${PROJECT_ROOT}/.venv"
COVERAGE_MIN_THRESHOLD=85
COVERAGE_REPORT_DIR="${PROJECT_ROOT}/htmlcov"
TEST_RESULTS_DIR="${PROJECT_ROOT}/test-results"

# Help text
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Run the dev-env test suite with various options.

OPTIONS:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -q, --quiet             Suppress non-essential output
    -f, --fast              Run fast tests only (skip slow/integration tests)
    -c, --coverage          Generate coverage report (default: enabled)
    --no-coverage           Disable coverage reporting
    --unit                  Run unit tests only
    --integration           Run integration tests only
    --error-scenarios       Run error scenario tests only
    --ci                    CI mode (stricter settings, JUnit XML output)
    --setup-only            Only setup environment, don't run tests
    --cleanup               Clean up test artifacts and coverage files
    --parallel              Run tests in parallel (requires pytest-xdist)

EXAMPLES:
    $0                      Run all tests with coverage
    $0 --fast              Run fast tests only
    $0 --unit              Run unit tests only
    $0 --ci                Run in CI mode
    $0 --cleanup           Clean up test artifacts

ENVIRONMENT VARIABLES:
    PYTEST_ARGS            Additional arguments to pass to pytest
    COVERAGE_MIN           Minimum coverage threshold (default: $COVERAGE_MIN_THRESHOLD)
    CI                     Set to 'true' to enable CI mode automatically
EOF
}

# Parse command line arguments
VERBOSE=false
QUIET=false
FAST_ONLY=false
COVERAGE_ENABLED=true
UNIT_ONLY=false
INTEGRATION_ONLY=false
ERROR_SCENARIOS_ONLY=false
CI_MODE=false
SETUP_ONLY=false
CLEANUP=false
PARALLEL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            HELPERS_UTILS_VERBOSE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            HELPERS_UTILS_QUIET=true
            shift
            ;;
        -f|--fast)
            FAST_ONLY=true
            shift
            ;;
        -c|--coverage)
            COVERAGE_ENABLED=true
            shift
            ;;
        --no-coverage)
            COVERAGE_ENABLED=false
            shift
            ;;
        --unit)
            UNIT_ONLY=true
            shift
            ;;
        --integration)
            INTEGRATION_ONLY=true
            shift
            ;;
        --error-scenarios)
            ERROR_SCENARIOS_ONLY=true
            shift
            ;;
        --ci)
            CI_MODE=true
            shift
            ;;
        --setup-only)
            SETUP_ONLY=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Auto-detect CI mode
if [[ "${CI:-false}" == "true" ]]; then
    CI_MODE=true
    log_info "CI environment detected, enabling CI mode"
fi

# Override coverage threshold if set in environment
if [[ -n "${COVERAGE_MIN:-}" ]]; then
    COVERAGE_MIN_THRESHOLD="$COVERAGE_MIN"
fi

# Function to setup Python environment
setup_environment() {
    log_info "Setting up Python environment..."
    
    cd "$PROJECT_ROOT"
    
    # Check if virtual environment exists
    if [[ ! -d "$VENV_PATH" ]]; then
        log_info "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
    fi
    
    # Activate virtual environment
    # shellcheck source=/dev/null
    source "$VENV_PATH/bin/activate"
    
    # Verify Python version
    python_version=$(python --version 2>&1 | cut -d' ' -f2)
    log_info "Using Python $python_version"
    
    # Check if dev dependencies are installed
    if ! python -c "import pytest" 2>/dev/null; then
        log_info "Installing development dependencies..."
        if command_exists uv; then
            uv sync --group dev
        else
            pip install --upgrade pip
            pip install -e .
            # Install dev dependencies manually if no uv
            pip install pytest>=8.3.5 pytest-cov>=6.1.1 pytest-mock>=3.14.1
        fi
    fi
    
    # Install package in editable mode
    log_info "Installing dev-env in editable mode..."
    pip install -e . >/dev/null 2>&1
    
    log_success "Environment setup complete"
}

# Function to clean up test artifacts
cleanup_artifacts() {
    cd "$PROJECT_ROOT"
    cleanup_files ".coverage" ".coverage.*" "htmlcov" ".pytest_cache" "test-results" "__pycache__" "*.pyc"
}

# Function to run linting and code quality checks
run_quality_checks() {
    if [[ "$CI_MODE" == "true" ]] || [[ "$VERBOSE" == "true" ]]; then
        log_info "Running code quality checks..."
        
        # Run ruff linting
        if command_exists ruff; then
            log_info "Running ruff linter..."
            ruff check src/ tests/ || {
                log_error "Ruff linting failed"
                return 1
            }
            
            log_info "Running ruff formatter..."
            ruff format --check src/ tests/ || {
                log_error "Code formatting check failed"
                return 1
            }
        else
            log_warning "Ruff not available, skipping linting"
        fi
        
        # Run mypy type checking
        if command_exists mypy; then
            log_info "Running mypy type checking..."
            mypy src/ || {
                log_warning "Type checking found issues (non-blocking)"
            }
        else
            log_warning "Mypy not available, skipping type checking"
        fi
        
        log_success "Code quality checks complete"
    fi
}

# Function to build pytest arguments
build_pytest_args() {
    local args=()
    
    # Base arguments
    if [[ "$VERBOSE" == "true" ]]; then
        args+=("-v")
    elif [[ "$QUIET" == "true" ]]; then
        args+=("-q")
    fi
    
    # Coverage arguments
    if [[ "$COVERAGE_ENABLED" == "true" ]]; then
        args+=("--cov=src/dev_env")
        args+=("--cov-report=term-missing")
        args+=("--cov-report=html:$COVERAGE_REPORT_DIR")
        args+=("--cov-fail-under=$COVERAGE_MIN_THRESHOLD")
        
        if [[ "$CI_MODE" == "true" ]]; then
            args+=("--cov-report=xml:coverage.xml")
        fi
    else
        args+=("--no-cov")
    fi
    
    # CI mode arguments
    if [[ "$CI_MODE" == "true" ]]; then
        mkdir -p "$TEST_RESULTS_DIR"
        args+=("--junitxml=$TEST_RESULTS_DIR/junit.xml")
        args+=("--tb=short")
        args+=("--strict-markers")
    fi
    
    # Parallel execution
    if [[ "$PARALLEL" == "true" ]]; then
        if python -c "import xdist" 2>/dev/null; then
            args+=("-n" "auto")
        else
            log_warning "pytest-xdist not available, running tests sequentially"
        fi
    fi
    
    # Test selection
    if [[ "$FAST_ONLY" == "true" ]]; then
        args+=("-m" "not slow")
    elif [[ "$UNIT_ONLY" == "true" ]]; then
        args+=("tests/test_config.py" "tests/test_state.py" "tests/test_docker.py" "tests/test_utils.py")
    elif [[ "$INTEGRATION_ONLY" == "true" ]]; then
        args+=("tests/test_integration.py")
    elif [[ "$ERROR_SCENARIOS_ONLY" == "true" ]]; then
        args+=("tests/test_error_scenarios.py")
    else
        args+=("tests/")
    fi
    
    # Add any additional pytest arguments from environment
    if [[ -n "${PYTEST_ARGS:-}" ]]; then
        # shellcheck disable=SC2206
        args+=($PYTEST_ARGS)
    fi
    
    echo "${args[@]}"
}

# Function to run tests
run_tests() {
    log_info "Running tests..."
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment
    # shellcheck source=/dev/null
    source "$VENV_PATH/bin/activate"
    
    # Set PYTHONPATH to include src directory
    export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"
    
    # Build pytest arguments
    local pytest_args
    pytest_args=$(build_pytest_args)
    
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "Running: pytest $pytest_args"
    fi
    
    # Run the tests
    # shellcheck disable=SC2086
    if python -m pytest $pytest_args; then
        log_success "All tests passed!"
        return 0
    else
        log_error "Some tests failed"
        return 1
    fi
}

# Function to display test summary
display_summary() {
    if [[ "$COVERAGE_ENABLED" == "true" ]] && [[ -f "$COVERAGE_REPORT_DIR/index.html" ]]; then
        log_info "Coverage report generated: $COVERAGE_REPORT_DIR/index.html"
    fi
    
    if [[ "$CI_MODE" == "true" ]] && [[ -f "$TEST_RESULTS_DIR/junit.xml" ]]; then
        log_info "JUnit XML report generated: $TEST_RESULTS_DIR/junit.xml"
    fi
    
    if [[ -f "coverage.xml" ]]; then
        log_info "Coverage XML report generated: coverage.xml"
    fi
}

# Main execution
main() {
    start_timer "test_run"
    
    log_info "Starting dev-env test runner..."
    log_info "Project root: $PROJECT_ROOT"
    
    # Handle cleanup mode
    if [[ "$CLEANUP" == "true" ]]; then
        cleanup_artifacts
        exit 0
    fi
    
    # Setup environment
    setup_environment
    
    # Handle setup-only mode
    if [[ "$SETUP_ONLY" == "true" ]]; then
        log_success "Environment setup complete"
        exit 0
    fi
    
    # Run quality checks
    if ! run_quality_checks; then
        if [[ "$CI_MODE" == "true" ]]; then
            log_error "Quality checks failed in CI mode"
            exit 1
        else
            log_warning "Quality checks failed, continuing with tests..."
        fi
    fi
    
    # Run tests
    local test_exit_code=0
    if ! run_tests; then
        test_exit_code=1
    fi
    
    # Display summary
    display_summary
    
    if [[ $test_exit_code -eq 0 ]]; then
        log_timer "test_run"
        log_success "Test run completed successfully"
    else
        log_timer "test_run"
        log_error "Test run failed"
    fi
    
    exit $test_exit_code
}

# Run main function
main "$@"