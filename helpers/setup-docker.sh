#!/usr/bin/env bash
# docker-remote - Remote Docker management via SSH config hosts
# Relies on properly configured SSH hosts in ~/.ssh/config

set -euo pipefail

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/utils.sh"

# Configuration
readonly CONFIG_DIR="${HOME}/.local/opt/dev-env/docker-remote"
readonly SOCKET_DIR="/tmp/docker-remote"
readonly DEFAULT_DOCKER_SOCKET="/var/run/docker.sock"

# Script metadata
readonly SCRIPT_NAME="docker-remote"
readonly VERSION="2.0.0"

# Usage information
usage() {
    cat << EOF
Usage: $0 COMMAND [OPTIONS]

Manage remote Docker connections via SSH config hosts.

COMMANDS:
    add NAME SSH_HOST      Configure remote Docker via SSH host
    connect NAME           Connect to remote Docker
    disconnect NAME        Disconnect from remote Docker
    list                  List configured connections
    remove NAME           Remove configuration
    status                Show active connections

OPTIONS:
    -s, --socket PATH     Remote Docker socket (default: $DEFAULT_DOCKER_SOCKET)
    -v, --verbose         Enable verbose output
    -q, --quiet           Suppress informational messages

EXAMPLES:
    # Assuming ~/.ssh/config contains:
    # Host docker-prod
    #     HostName 192.168.1.100
    #     User ubuntu
    #     IdentityFile ~/.ssh/prod-key
    
    $0 add prod docker-prod
    $0 connect prod
    docker ps  # Uses remote Docker
    $0 disconnect prod

SSH CONFIG:
    This tool relies on SSH hosts configured in ~/.ssh/config.
    Ensure your SSH config has proper host entries with key authentication.
EOF
}

# Initialize environment
init_environment() {
    log_debug "Initializing $SCRIPT_NAME v$VERSION"
    
    # Ensure required commands exist
    require_command "ssh" "OpenSSH is required"
    require_command "docker" "Docker CLI is required"
    
    # Create directories if needed
    mkdir -p "$CONFIG_DIR" "$SOCKET_DIR"
    
    log_debug "Configuration directory: $CONFIG_DIR"
    log_debug "Socket directory: $SOCKET_DIR"
}

# Save connection configuration
save_config() {
    local name="$1"
    local ssh_host="$2"
    local docker_socket="$3"
    local config_file="$CONFIG_DIR/$name.conf"
    
    log_debug "Saving configuration for $name to $config_file"
    
    cat > "$config_file" << EOF
# Docker remote configuration for $name
# Generated: $(date)
SSH_HOST=$ssh_host
DOCKER_SOCKET=$docker_socket
LOCAL_SOCKET=$SOCKET_DIR/$name.sock
EOF
    
    log_success "Saved configuration for $name"
}

# Load configuration
load_config() {
    local name="$1"
    local config_file="$CONFIG_DIR/$name.conf"
    
    log_debug "Loading configuration from $config_file"
    
    if [[ ! -f "$config_file" ]]; then
        log_error "Configuration '$name' not found"
        local configs=$(ls -1 "$CONFIG_DIR"/*.conf 2>/dev/null | xargs -n1 basename -s .conf | tr '\n' ' ')
        [[ -n "$configs" ]] && log_info "Available configurations: $configs"
        return 1
    fi
    
    source "$config_file"
    log_debug "Loaded: SSH_HOST=$SSH_HOST, DOCKER_SOCKET=$DOCKER_SOCKET"
}

# Test SSH connection using SSH config host
test_ssh_connection() {
    local ssh_host="$1"
    
    log_progress "Testing SSH connection to $ssh_host..."
    
    # Test basic SSH connectivity
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_host" "true" 2>/dev/null; then
        log_success "SSH connection successful"
        return 0
    else
        log_error "SSH connection failed to $ssh_host"
        log_info "Please check:"
        log_info "  - SSH host '$ssh_host' exists in ~/.ssh/config"
        log_info "  - SSH keys are properly configured"
        log_info "  - Remote host is reachable"
        return 1
    fi
}

# Test Docker on remote host
test_remote_docker() {
    local ssh_host="$1"
    local docker_socket="$2"
    
    log_progress "Testing Docker on remote host..."
    
    # Test Docker socket existence
    if ! ssh "$ssh_host" "test -S $docker_socket" 2>/dev/null; then
        log_error "Docker socket not found at $docker_socket"
        return 1
    fi
    
    # Test Docker accessibility
    local docker_version
    if docker_version=$(ssh "$ssh_host" "docker version --format 'Server: {{.Server.Version}}'" 2>&1); then
        log_success "Docker is accessible ($docker_version)"
        return 0
    else
        log_error "Docker not accessible on remote host"
        log_info "Please ensure:"
        log_info "  - Docker is running on remote host"
        log_info "  - User has permission to access Docker"
        log_debug "Error output: $docker_version"
        return 1
    fi
}

# Add new remote host
cmd_add() {
    local name="$1"
    local ssh_host="$2"
    local docker_socket="${DOCKER_SOCKET:-$DEFAULT_DOCKER_SOCKET}"
    
    if [[ -z "$name" || -z "$ssh_host" ]]; then
        log_error "Missing required arguments"
        echo "Usage: $0 add NAME SSH_HOST" >&2
        return 1
    fi
    
    log_info "Adding remote Docker connection '$name' via SSH host '$ssh_host'"
    
    # Validate connection name
    if [[ "$name" =~ [^a-zA-Z0-9_-] ]]; then
        log_error "Name can only contain letters, numbers, underscores, and hyphens"
        return 1
    fi
    
    # Check if already exists
    if [[ -f "$CONFIG_DIR/$name.conf" ]]; then
        log_warning "Configuration '$name' already exists"
        read -p "Overwrite? [y/N] " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && return 1
    fi
    
    # Test connection
    start_timer "connection_test"
    test_ssh_connection "$ssh_host" || return 1
    test_remote_docker "$ssh_host" "$docker_socket" || return 1
    log_timer "connection_test"
    
    # Save configuration
    save_config "$name" "$ssh_host" "$docker_socket"
}

# Connect to remote Docker
cmd_connect() {
    local name="$1"
    
    if [[ -z "$name" ]]; then
        log_error "Missing required argument"
        echo "Usage: $0 connect NAME" >&2
        return 1
    fi
    
    log_info "Connecting to '$name'"
    
    # Load configuration
    load_config "$name" || return 1
    
    # Check if already connected
    if [[ -S "$LOCAL_SOCKET" ]]; then
        # Verify socket is working
        if docker --host "unix://$LOCAL_SOCKET" version &>/dev/null; then
            log_info "Already connected to $name"
            log_info "Docker socket: $LOCAL_SOCKET"
            return 0
        else
            log_warning "Stale socket detected, reconnecting..."
            rm -f "$LOCAL_SOCKET"
        fi
    fi
    
    # Start SSH tunnel using SSH config host
    log_progress "Establishing SSH tunnel to $SSH_HOST..."
    
    local control_socket="$SOCKET_DIR/$name.ctl"
    
    # Clean up any existing control socket
    [[ -S "$control_socket" ]] && ssh -S "$control_socket" -O exit "$SSH_HOST" 2>/dev/null || true
    
    # Create SSH tunnel with all options handled by SSH config
    if ! ssh -fN \
        -o "ControlMaster=auto" \
        -o "ControlPath=$control_socket" \
        -o "ControlPersist=10m" \
        -o "ExitOnForwardFailure=yes" \
        -L "$LOCAL_SOCKET:$DOCKER_SOCKET" \
        "$SSH_HOST"; then
        log_error "Failed to establish SSH tunnel"
        return 1
    fi
    
    # Wait for socket with timeout
    log_progress "Waiting for Docker socket..."
    local count=0
    while [[ ! -S "$LOCAL_SOCKET" && $count -lt 20 ]]; do
        sleep 0.25
        ((count++))
    done
    
    if [[ ! -S "$LOCAL_SOCKET" ]]; then
        log_error "Socket not created after timeout"
        ssh -S "$control_socket" -O exit "$SSH_HOST" 2>/dev/null || true
        return 1
    fi
    
    # Verify Docker connection
    if ! docker --host "unix://$LOCAL_SOCKET" version &>/dev/null; then
        log_error "Docker connection test failed"
        ssh -S "$control_socket" -O exit "$SSH_HOST" 2>/dev/null || true
        rm -f "$LOCAL_SOCKET"
        return 1
    fi
    
    log_success "Connected to $name"
    
    # Create Docker context
    log_progress "Creating Docker context..."
    if docker context create "$name" \
        --description "Remote: $SSH_HOST" \
        --docker "host=unix://$LOCAL_SOCKET" &>/dev/null; then
        log_success "Created Docker context '$name'"
    else
        log_debug "Context may already exist"
    fi
    
    # Create buildx builder
    log_progress "Creating buildx builder..."
    if docker buildx create \
        --name "$name" \
        --driver docker-container \
        --driver-opt network=host \
        --use \
        "unix://$LOCAL_SOCKET" &>/dev/null; then
        log_success "Created buildx builder '$name' (active)"
    else
        log_debug "Builder may already exist"
    fi
    
    # Show connection info
    echo
    log_info "Connection established. To use:"
    echo "  export DOCKER_HOST=unix://$LOCAL_SOCKET"
    echo "  # or"
    echo "  docker --context $name <command>"
    echo "  # or for buildx"
    echo "  docker buildx build --builder $name ."
}

# Disconnect from remote Docker
cmd_disconnect() {
    local name="$1"
    
    if [[ -z "$name" ]]; then
        log_error "Missing required argument"
        echo "Usage: $0 disconnect NAME" >&2
        return 1
    fi
    
    log_info "Disconnecting from '$name'"
    
    # Load configuration (ignore errors if not found)
    if load_config "$name" 2>/dev/null; then
        # Stop SSH tunnel using control socket
        local control_socket="$SOCKET_DIR/$name.ctl"
        if [[ -S "$control_socket" ]]; then
            log_progress "Stopping SSH tunnel..."
            if ssh -S "$control_socket" -O exit "$SSH_HOST" 2>/dev/null; then
                log_success "SSH tunnel stopped"
            fi
        fi
        
        # Clean up socket
        if [[ -S "$LOCAL_SOCKET" ]]; then
            rm -f "$LOCAL_SOCKET"
            log_debug "Removed socket $LOCAL_SOCKET"
        fi
    fi
    
    # Always try to clean up Docker resources
    # Remove Docker context
    if docker context ls --format '{{.Name}}' | grep -q "^${name}$"; then
        log_progress "Removing Docker context..."
        docker context rm -f "$name" &>/dev/null || true
        log_success "Removed Docker context"
    fi
    
    # Remove buildx builder
    if docker buildx ls | grep -q "^${name} "; then
        log_progress "Removing buildx builder..."
        docker buildx rm -f "$name" &>/dev/null || true
        log_success "Removed buildx builder"
    fi
    
    log_success "Disconnected from $name"
}

# List configurations
cmd_list() {
    log_info "Docker remote connections:"
    echo
    
    local found=0
    printf "%-20s %-30s %-20s %s\n" "NAME" "SSH HOST" "DOCKER SOCKET" "STATUS"
    printf "%-20s %-30s %-20s %s\n" "----" "--------" "-------------" "------"
    
    for conf in "$CONFIG_DIR"/*.conf; do
        [[ -f "$conf" ]] || continue
        found=1
        
        local name=$(basename "$conf" .conf)
        source "$conf"
        
        local status="${RED}inactive${NC}"
        if [[ -S "$LOCAL_SOCKET" ]]; then
            # Test if socket is actually working
            if docker --host "unix://$LOCAL_SOCKET" version &>/dev/null; then
                status="${GREEN}active${NC}"
            else
                status="${YELLOW}stale${NC}"
            fi
        fi
        
        printf "%-20s %-30s %-20s " "$name" "$SSH_HOST" "$DOCKER_SOCKET"
        echo -e "$status"
    done
    
    if [[ $found -eq 0 ]]; then
        log_info "No connections configured"
        log_info "Add one with: $0 add NAME SSH_HOST"
    fi
}

# Show status
cmd_status() {
    log_info "Docker Remote Status"
    echo
    
    # Active connections
    log_info "Active connections:"
    local active=0
    for sock in "$SOCKET_DIR"/*.sock; do
        [[ -S "$sock" ]] || continue
        active=1
        
        local name=$(basename "$sock" .sock)
        printf "  %-20s " "$name"
        
        if docker --host "unix://$sock" version --format 'Server: {{.Server.Version}}' 2>&1 >/dev/null; then
            local version=$(docker --host "unix://$sock" version --format '{{.Server.Version}}' 2>/dev/null)
            echo -e "${GREEN}healthy${NC} (Docker $version)"
        else
            echo -e "${RED}unhealthy${NC}"
        fi
    done
    
    [[ $active -eq 0 ]] && echo "  (none)"
    
    # SSH tunnels
    echo
    log_info "SSH tunnels:"
    local tunnels=0
    for ctl in "$SOCKET_DIR"/*.ctl; do
        [[ -S "$ctl" ]] || continue
        tunnels=1
        
        local name=$(basename "$ctl" .ctl)
        local ssh_host=""
        
        # Load config to get SSH host
        if [[ -f "$CONFIG_DIR/$name.conf" ]]; then
            source "$CONFIG_DIR/$name.conf"
            printf "  %-20s %s" "$name" "$SSH_HOST"
            
            # Check tunnel status
            if ssh -S "$ctl" -O check "$SSH_HOST" 2>/dev/null; then
                echo -e " ${GREEN}[alive]${NC}"
            else
                echo -e " ${RED}[dead]${NC}"
            fi
        fi
    done
    
    [[ $tunnels -eq 0 ]] && echo "  (none)"
    
    # Docker contexts
    echo
    log_info "Docker contexts:"
    docker context ls --format "  {{.Name}}: {{.DockerEndpoint}}" | grep -v "^  default:" || echo "  (none)"
    
    # Buildx builders
    echo
    log_info "Buildx builders:"
    docker buildx ls --format "  {{.Name}}: {{.DriverEndpoint}}" | grep -v "^  default:" || echo "  (none)"
}

# Remove configuration
cmd_remove() {
    local name="$1"
    
    if [[ -z "$name" ]]; then
        log_error "Missing required argument"
        echo "Usage: $0 remove NAME" >&2
        return 1
    fi
    
    log_info "Removing connection '$name'"
    
    # Disconnect first (ignore errors)
    cmd_disconnect "$name" &>/dev/null || true
    
    # Remove config file
    local config_file="$CONFIG_DIR/$name.conf"
    if [[ -f "$config_file" ]]; then
        rm -f "$config_file"
        log_success "Removed configuration"
    else
        log_warning "Configuration not found"
    fi
}

# Cleanup function for exit
cleanup_on_exit() {
    log_debug "Cleaning up..."
}

# Main function
main() {
    # Initialize
    init_environment
    set_exit_handler cleanup_on_exit
    
    # Parse global options
    local DOCKER_SOCKET=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--socket)
                DOCKER_SOCKET="$2"
                shift 2
                ;;
            -v|--verbose)
                HELPERS_UTILS_VERBOSE=true
                shift
                ;;
            -q|--quiet)
                HELPERS_UTILS_QUIET=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            --version)
                echo "$SCRIPT_NAME version $VERSION"
                exit 0
                ;;
            -*)
                log_error "Unknown option: $1"
                usage >&2
                exit 1
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Get command
    local command="${1:-}"
    [[ -z "$command" ]] && { usage >&2; exit 1; }
    shift
    
    # Execute command
    case "$command" in
        add)
            cmd_add "$@"
            ;;
        connect)
            cmd_connect "$@"
            ;;
        disconnect)
            cmd_disconnect "$@"
            ;;
        list)
            cmd_list
            ;;
        status)
            cmd_status
            ;;
        remove)
            cmd_remove "$@"
            ;;
        *)
            log_error "Unknown command: $command"
            usage >&2
            exit 1
            ;;
    esac
}

# Execute main if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi