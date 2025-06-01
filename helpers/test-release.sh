#!/bin/bash
# smoke-test.sh - End-to-end smoke test for dev-env releases
# Creates an environment, performs operations, and tears it down

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source utilities
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Exit codes
readonly EXIT_SUCCESS=0
readonly EXIT_SETUP_FAILED=1
readonly EXIT_COMMAND_FAILED=2
readonly EXIT_CLEANUP_FAILED=3

# Test configuration
readonly TEST_ENV_NAME="smoke-test-env"
readonly TEST_CONFIG_FILE="smoke-test-config.py"
readonly TEST_TIMEOUT=300  # 5 minutes max

# Cleanup function
cleanup() {
    local exit_code=$?
    
    log_info "Cleaning up test artifacts"
    
    # Remove test config file
    if [[ -f "$TEST_CONFIG_FILE" ]]; then
        rm -f "$TEST_CONFIG_FILE"
    fi
    
    # Ensure environment is removed
    if dev-env list | grep -q "$TEST_ENV_NAME"; then
        log_info "Removing test environment"
        dev-env down "$TEST_ENV_NAME" --volumes || true
    fi
    
    return $exit_code
}

# Create test configuration
create_test_config() {
    log_progress "Creating test configuration"
    
    cat > "$TEST_CONFIG_FILE" << 'EOF'
from dev_env.config import Environment, VolumeMount

# Minimal test environment
environment = Environment(
    name="smoke-test-env",
    base_image="python:3.13-slim",
    command=["/bin/tail", "-f", "/dev/null"],
    ports={
        22: {"HostPort": 2299}  # Non-standard port for testing
    },
    volumes=[
        VolumeMount(
            source="smoke-test-data",
            target="/data",
            type="named"
        )
    ],
    environment={
        "TEST_VAR": "smoke_test_value",
        "PYTHONUNBUFFERED": "1"
    },
    memory="512m",
    cpus=1.0
)
EOF
    
    log_success "Test configuration created"
}

# Run a command and check result
run_test_command() {
    local description="$1"
    shift
    local command=("$@")
    
    log_progress "$description"
    if "${command[@]}"; then
        log_success "$description - PASSED"
        return 0
    else
        log_error "$description - FAILED"
        return 1
    fi
}

# Main test function
main() {
    log_info "Starting dev-env smoke test"
    start_timer "smoke_test"
    
    # Change to project root
    cd "$(get_project_root)"
    
    # Check prerequisites
    log_progress "Checking prerequisites"
    if ! command_exists dev-env; then
        # Try to use the local version
        if [[ -f "src/dev_env/__main__.py" ]]; then
            alias dev-env="python -m dev_env"
        else
            log_error "dev-env command not found"
            exit $EXIT_SETUP_FAILED
        fi
    fi
    
    # 1. Create test configuration
    create_test_config
    
    # 2. Test: Create and start environment
    run_test_command "Creating environment" \
        dev-env up "$TEST_CONFIG_FILE" || exit $EXIT_COMMAND_FAILED
    
    # Wait for container to be ready
    sleep 5
    
    # 3. Test: List environments
    run_test_command "Listing environments" \
        dev-env list || exit $EXIT_COMMAND_FAILED
    
    # Verify our environment appears in the list
    if ! dev-env list | grep -q "$TEST_ENV_NAME.*running"; then
        log_error "Environment not found or not running"
        exit $EXIT_COMMAND_FAILED
    fi
    
    # 4. Test: Execute simple command
    run_test_command "Executing echo command" \
        dev-env exec "$TEST_ENV_NAME" echo "Hello from smoke test" || exit $EXIT_COMMAND_FAILED
    
    # 5. Test: Execute Python command
    run_test_command "Executing Python command" \
        dev-env exec "$TEST_ENV_NAME" python -c "print('Python works!')" || exit $EXIT_COMMAND_FAILED
    
    # 6. Test: Check environment variable
    run_test_command "Checking environment variable" \
        dev-env exec "$TEST_ENV_NAME" sh -c 'test "$TEST_VAR" = "smoke_test_value"' || exit $EXIT_COMMAND_FAILED
    
    # 7. Test: Write to volume
    run_test_command "Writing to volume" \
        dev-env exec "$TEST_ENV_NAME" sh -c "echo 'test data' > /data/test.txt" || exit $EXIT_COMMAND_FAILED
    
    # 8. Test: Read from volume
    run_test_command "Reading from volume" \
        dev-env exec "$TEST_ENV_NAME" cat /data/test.txt || exit $EXIT_COMMAND_FAILED
    
    # 9. Test: Show logs
    run_test_command "Showing logs" \
        dev-env logs "$TEST_ENV_NAME" --tail 10 || exit $EXIT_COMMAND_FAILED
    
    # 10. Test: SSH connectivity (if possible)
    if command_exists ssh; then
        log_progress "Testing SSH connectivity"
        # Just check if SSH port is listening
        if nc -z localhost 2299 2>/dev/null; then
            log_success "SSH port is accessible"
        else
            log_warning "SSH port not accessible (might be expected in CI)"
        fi
    fi
    
    # 11. Test: Install package in container
    run_test_command "Installing package in container" \
        dev-env exec "$TEST_ENV_NAME" pip install --no-cache-dir requests || exit $EXIT_COMMAND_FAILED
    
    # 12. Test: Run installed package
    run_test_command "Testing installed package" \
        dev-env exec "$TEST_ENV_NAME" python -c "import requests; print('requests version:', requests.__version__)" || exit $EXIT_COMMAND_FAILED
    
    # 13. Test: Stop environment
    run_test_command "Stopping environment" \
        dev-env down "$TEST_ENV_NAME" || exit $EXIT_COMMAND_FAILED
    
    # 14. Test: Verify environment is removed
    if dev-env list | grep -q "$TEST_ENV_NAME"; then
        log_error "Environment still exists after removal"
        exit $EXIT_CLEANUP_FAILED
    fi
    
    # 15. Test: Remove volumes
    run_test_command "Recreating environment for volume test" \
        dev-env up "$TEST_CONFIG_FILE" || exit $EXIT_COMMAND_FAILED
    
    sleep 5
    
    run_test_command "Removing environment with volumes" \
        dev-env down "$TEST_ENV_NAME" --volumes || exit $EXIT_COMMAND_FAILED
    
    log_timer "smoke_test"
    log_success "All smoke tests passed!"
    
    exit $EXIT_SUCCESS
}

# Advanced test mode (optional)
run_advanced_tests() {
    log_info "Running advanced smoke tests"
    
    # Test: Multiple environments
    log_progress "Testing multiple environments"
    
    # Create second config
    cat > "smoke-test-config-2.py" << 'EOF'
from dev_env.config import Environment

environment = Environment(
    name="smoke-test-env-2",
    base_image="alpine:latest",
    command=["sh", "-c", "while true; do sleep 30; done"],
    ports={
        8080: {"HostPort": 8088}
    }
)
EOF
    
    # Start second environment
    if dev-env up "smoke-test-config-2.py"; then
        log_success "Second environment created"
        
        # Verify both are running
        local count=$(dev-env list | grep -c "smoke-test-env.*running" || true)
        if [[ "$count" -eq 2 ]]; then
            log_success "Multiple environments running"
        else
            log_error "Expected 2 environments, found $count"
        fi
        
        # Clean up second environment
        dev-env down "smoke-test-env-2" --volumes || true
        rm -f "smoke-test-config-2.py"
    else
        log_warning "Multiple environment test failed"
    fi
}

# Parse command line arguments
ADVANCED_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --advanced)
            ADVANCED_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --advanced    Run additional advanced tests"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set cleanup trap
trap cleanup EXIT

# Run tests
main

# Run advanced tests if requested
if [[ "$ADVANCED_MODE" == "true" ]]; then
    run_advanced_tests
fi