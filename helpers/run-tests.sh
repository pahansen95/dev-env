#!/usr/bin/env bash
set -euo pipefail

# run-tests.sh - Simplified test runner for CI/CD integration
# Provides standardized test execution with minimal complexity

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/utils.sh"

# Configuration defaults
readonly DEFAULT_OUTPUT_DIR=".test-results"
readonly DEFAULT_COVERAGE_THRESHOLD=70
readonly PYTHON_MIN_VERSION="3.13"

# Script variables
test_type="all"
coverage_enabled=""
output_format=""
output_dir="$DEFAULT_OUTPUT_DIR"
coverage_threshold="$DEFAULT_COVERAGE_THRESHOLD"
declare -a pytest_args=()

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_TEST_FAILED=1
readonly EXIT_INVALID_ARGS=2
readonly EXIT_MISSING_DEPS=3
readonly EXIT_COVERAGE_FAILED=4

show_help() {
    cat << EOF
Usage: $0 [OPTIONS] [-- PYTEST_ARGS]

Standardized test runner for CI/CD pipelines.

OPTIONS:
    --type TYPE        Test type: all|unit|integration|smoke (default: all)
    --coverage [BOOL]  Enable/disable coverage (yes|no, default: no, yes in CI)
    --format FORMAT    Output format: terminal|junit|json (default: terminal, junit in CI)
    --output DIR       Output directory for reports (default: $DEFAULT_OUTPUT_DIR)
    --fail-under PCT   Coverage threshold percentage (default: $DEFAULT_COVERAGE_THRESHOLD)
    -h, --help         Show this help message

PYTEST_ARGS:
    Additional arguments passed directly to pytest

EXAMPLES:
    $0                                    # Run all tests with defaults
    $0 --type unit --coverage            # Run unit tests with coverage
    $0 --coverage no                     # Explicitly disable coverage
    $0 --format junit --output results/  # Generate JUnit report
    $0 --type smoke -- -v -s            # Run smoke tests with pytest verbose

EXIT CODES:
    0 - All tests passed
    1 - Test failures
    2 - Invalid arguments
    3 - Missing dependencies
    4 - Coverage below threshold
EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)
                if [[ $# -lt 2 ]]; then
                    log_error "Option --type requires an argument"
                    exit $EXIT_INVALID_ARGS
                fi
                test_type="$2"
                shift 2
                ;;
            --coverage)
                if [[ $# -gt 1 ]] && [[ "$2" =~ ^(yes|no)$ ]]; then
                    coverage_enabled="$2"
                    shift 2
                else
                    coverage_enabled="yes"
                    shift
                fi
                ;;
            --format)
                if [[ $# -lt 2 ]]; then
                    log_error "Option --format requires an argument"
                    exit $EXIT_INVALID_ARGS
                fi
                output_format="$2"
                shift 2
                ;;
            --output)
                if [[ $# -lt 2 ]]; then
                    log_error "Option --output requires an argument"
                    exit $EXIT_INVALID_ARGS
                fi
                output_dir="$2"
                shift 2
                ;;
            --fail-under)
                if [[ $# -lt 2 ]]; then
                    log_error "Option --fail-under requires an argument"
                    exit $EXIT_INVALID_ARGS
                fi
                coverage_threshold="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit $EXIT_SUCCESS
                ;;
            --)
                shift
                pytest_args=("$@")
                break
                ;;
            *)
                log_error "Unknown option: $1"
                show_help >&2
                exit $EXIT_INVALID_ARGS
                ;;
        esac
    done
    
    # Apply CI defaults
    if [[ "${CI:-false}" == "true" ]]; then
        : ${coverage_enabled:="yes"}
        : ${output_format:="junit"}
    else
        : ${coverage_enabled:="no"}
        : ${output_format:="terminal"}
    fi
    
    # Validate arguments
    case "$test_type" in
        all|unit|integration|smoke) ;;
        *)
            log_error "Invalid test type '$test_type' - use: all|unit|integration|smoke"
            exit $EXIT_INVALID_ARGS
            ;;
    esac
    
    case "$output_format" in
        terminal|junit|json) ;;
        *)
            log_error "Invalid output format '$output_format' - use: terminal|junit|json"
            exit $EXIT_INVALID_ARGS
            ;;
    esac
    
    if [[ ! "$coverage_threshold" =~ ^[0-9]+$ ]] || [[ "$coverage_threshold" -lt 0 ]] || [[ "$coverage_threshold" -gt 100 ]]; then
        log_error "Invalid coverage threshold '$coverage_threshold' - must be 0-100"
        exit $EXIT_INVALID_ARGS
    fi
}

validate_environment() {
    log_info "Validating test environment..."
    
    # Check Python version
    if ! command_exists python3; then
        log_error "Python 3 not found"
        exit $EXIT_MISSING_DEPS
    fi
    
    local python_version
    python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    
    if [[ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$python_version" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]]; then
        log_error "Python $PYTHON_MIN_VERSION+ required (found: $python_version)"
        exit $EXIT_MISSING_DEPS
    fi
    
    # Check pytest availability
    if ! python3 -m pytest --version >/dev/null 2>&1; then
        log_error "pytest not found - run: pip install -e .[dev]"
        exit $EXIT_MISSING_DEPS
    fi
    
    # Check coverage plugin if needed
    if [[ "$coverage_enabled" == "yes" ]] && ! python3 -c "import pytest_cov" 2>/dev/null; then
        log_error "pytest-cov not found - run: pip install -e .[dev]"
        exit $EXIT_MISSING_DEPS
    fi
    
    # Check json plugin if needed
    if [[ "$output_format" == "json" ]] && ! python3 -c "import pytest_json_report" 2>/dev/null; then
        log_error "pytest-json-report not found - run: pip install pytest-json-report"
        exit $EXIT_MISSING_DEPS
    fi
    
    log_success "Environment validated"
}

build_pytest_command() {
    local -a cmd=(python3 -m pytest)
    
    # Add test selection based on type
    case "$test_type" in
        all)
            cmd+=(tests/)
            ;;
        unit)
            cmd+=(tests/test_config.py tests/test_state.py tests/test_docker.py tests/test_utils.py tests/test_cli.py tests/test_core.py)
            cmd+=(-m "not integration")
            ;;
        integration)
            cmd+=(tests/test_integration.py)
            ;;
        smoke)
            cmd+=(tests/test_core.py::TestEnvironmentConfig::test_minimal_environment)
            cmd+=(tests/test_core.py::TestDockerClient::test_docker_client_init)
            ;;
    esac
    
    # Add coverage options
    if [[ "$coverage_enabled" == "yes" ]]; then
        cmd+=(
            --cov=src/dev_env
            --cov-report=term-missing
            --cov-fail-under="$coverage_threshold"
        )
        
        # Add coverage output files
        mkdir -p "$output_dir"
        cmd+=(
            --cov-report="html:$output_dir/htmlcov"
            --cov-report="xml:$output_dir/coverage.xml"
        )
    fi
    
    # Add output format options
    case "$output_format" in
        junit)
            mkdir -p "$output_dir"
            cmd+=(--junit-xml="$output_dir/junit.xml")
            if [[ "${CI:-false}" != "true" ]]; then
                # Still show progress in terminal when generating JUnit locally
                cmd+=(-v)
            fi
            ;;
        json)
            mkdir -p "$output_dir"
            # Note: Requires pytest-json-report plugin
            cmd+=(--json-report --json-report-file="$output_dir/results.json")
            ;;
        terminal)
            # Use human-friendly output
            if [[ -t 1 ]]; then
                # Terminal supports colors
                cmd+=(--color=yes)
            fi
            cmd+=(-v)  # Verbose for better readability
            ;;
    esac
    
    # Add standard options for CI
    if [[ "${CI:-false}" == "true" ]]; then
        cmd+=(--tb=short --strict-markers)
    else
        # More detailed output for developers
        cmd+=(--tb=short --strict-markers --durations=10)
    fi
    
    # Add any user-provided pytest arguments
    if [[ ${#pytest_args[@]} -gt 0 ]]; then
        cmd+=("${pytest_args[@]}")
    fi
    
    echo "${cmd[@]}"
}

execute_tests() {
    local cmd
    cmd=$(build_pytest_command)
    
    echo
    log_info "Running $test_type tests..."
    log_debug "Command: $cmd"
    
    cd "$(get_project_root)"
    
    # Execute pytest and capture exit code
    local exit_code=0
    if ! $cmd; then
        exit_code=$?
        
        # Distinguish between test failures and coverage failures
        if [[ "$coverage_enabled" == "yes" ]] && grep -q "coverage.*below" "$output_dir/coverage.xml" 2>/dev/null; then
            echo
            log_error "Coverage below threshold $coverage_threshold%"
            return $EXIT_COVERAGE_FAILED
        else
            echo
            log_error "Test failures detected"
            return $EXIT_TEST_FAILED
        fi
    fi
    
    echo
    log_success "All tests passed successfully!"
    return $EXIT_SUCCESS
}

report_results() {
    echo
    log_info "Test Run Summary"
    log_info "================"
    
    # Report test configuration
    echo "  Test Type: $test_type"
    echo "  Coverage: $coverage_enabled"
    if [[ "$coverage_enabled" == "yes" ]]; then
        echo "  Coverage Threshold: $coverage_threshold%"
    fi
    echo
    
    # Report output locations
    if [[ -d "$output_dir" ]] && [[ "$output_format" != "terminal" || "$coverage_enabled" == "yes" ]]; then
        log_info "Generated Reports:"
        
        if [[ -f "$output_dir/junit.xml" ]]; then
            echo "  • JUnit XML: $output_dir/junit.xml"
        fi
        
        if [[ -f "$output_dir/coverage.xml" ]]; then
            echo "  • Coverage XML: $output_dir/coverage.xml"
        fi
        
        if [[ -d "$output_dir/htmlcov" ]]; then
            echo "  • Coverage HTML: $output_dir/htmlcov/index.html"
            if [[ "${CI:-false}" != "true" ]] && command_exists open 2>/dev/null; then
                echo "    (open with: open $output_dir/htmlcov/index.html)"
            fi
        fi
        
        if [[ -f "$output_dir/results.json" ]]; then
            echo "  • JSON Results: $output_dir/results.json"
        fi
    fi
}

main() {
    start_timer "test_execution"
    
    parse_arguments "$@"
    validate_environment
    
    echo
    log_info "Test Configuration"
    log_info "=================="
    echo "  Type: $test_type"
    echo "  Coverage: $coverage_enabled"
    echo "  Format: $output_format"
    echo "  Output: $output_dir"
    
    # Execute tests and handle exit code
    local test_exit_code=0
    if ! execute_tests; then
        test_exit_code=$?
    fi
    
    report_results
    
    echo
    log_timer "test_execution"
    echo
    
    exit $test_exit_code
}

# Execute main function
main "$@"