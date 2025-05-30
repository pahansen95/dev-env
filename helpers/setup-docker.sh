#!/bin/bash
# setup-docker.sh - Docker connection management with SSH, TLS, and TCP support
# Organized into three commands: api, ctx, buildx

set -euo pipefail

# Source shared utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/utils.sh"

# Configuration
readonly CONFIG_DIR="${HOME}/.docker-setup"
readonly SSH_CONTROL_DIR="${HOME}/.ssh/docker-forwards"
readonly DEFAULT_TLS_PORT="2376"
readonly DEFAULT_TCP_PORT="2375"

# Script state
TRANSPORT="ssh"
SSH_HOST=""
REMOTE_HOST=""
TLS_PORT="${DEFAULT_TLS_PORT}"
TCP_PORT="${DEFAULT_TCP_PORT}"
LOCAL_SOCKET=""
REMOTE_SOCKET="/var/run/docker.sock"
CERT_PATH=""
SKIP_VERIFY="false"
CONTEXT_NAME=""
BUILDX_NAME=""

# Usage information
usage() {
    cat << EOF
Usage: $0 COMMAND [OPTIONS] [TARGET]

Docker connection management with support for API, contexts, and buildx.

COMMANDS:
    api     Manage Docker API connections (sets DOCKER_HOST)
    ctx     Manage Docker contexts
    buildx  Manage Docker buildx builders

TRANSPORT OPTIONS:
    --ssh HOST          SSH forwarding via ~/.ssh/config host
    --tls HOST[:PORT]   Direct TLS connection (default port: ${DEFAULT_TLS_PORT})
    --tcp HOST[:PORT]   Plain TCP connection (default port: ${DEFAULT_TCP_PORT})

ACTIONS (for all commands):
    setup TARGET        Configure connection to target
    start               Start connection (SSH tunnels, etc.)
    stop                Stop connection
    restart             Restart connection
    remove              Remove configuration
    status              Show connection status
    test                Test connection

OPTIONS:
    --cert-path PATH    Path to TLS certificates directory
    --skip-verify       Skip TLS certificate verification
    --remote-socket PATH Remote socket path (default: ${REMOTE_SOCKET})
    -h, --help          Show this help message

EXAMPLES:
    # API Management
    $0 api --ssh myserver setup myserver      # Setup API via SSH
    $0 api --tls docker.example.com setup     # Setup API via TLS
    $0 api start                              # Start API connection
    $0 api status                             # Check API status

    # Context Management
    $0 ctx --ssh myserver setup myserver      # Setup context via SSH
    $0 ctx --name remote-dev setup myserver   # Setup named context
    $0 ctx start                              # Start context connection
    $0 ctx list                              # List contexts

    # Buildx Management
    $0 buildx --ssh myserver setup myserver   # Setup buildx via SSH
    $0 buildx --name remote-builder setup     # Setup named builder
    $0 buildx start                           # Start buildx connection
    $0 buildx list                           # List builders

SSH CONFIG INTEGRATION:
    When using --ssh, relies on ~/.ssh/config for connection details:
    
    Host myserver
        HostName docker.example.com
        User myuser
        Port 2222
        IdentityFile ~/.ssh/docker_key
        
TRANSPORT DETAILS:
    ssh:     Secure SSH socket forwarding (recommended)
    tls:     Direct TLS connection (requires certificates)
    tcp:     Plain TCP (insecure, development only)

NOTES:
    - SSH transport is recommended for security and simplicity
    - TLS transport requires proper certificate setup
    - TCP transport should only be used in trusted environments
    - Each command maintains separate configurations
    - Use 'source <($0 api start)' to set environment variables
EOF
}

# Parse command and options
parse_args() {
    local command=""
    local action=""
    local target=""
    
    # First argument must be command
    if [[ $# -eq 0 ]]; then
        log_error "Command is required"
        usage >&2
        exit 1
    fi
    
    command="$1"
    shift
    
    case "$command" in
        api|ctx|buildx)
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown command: $command"
            usage >&2
            exit 1
            ;;
    esac
    
    # Parse options and actions
    while [[ $# -gt 0 ]]; do
        case $1 in
            --ssh)
                TRANSPORT="ssh"
                SSH_HOST="$2"
                shift 2
                ;;
            --tls)
                TRANSPORT="tls"
                REMOTE_HOST="$2"
                shift 2
                ;;
            --tcp)
                TRANSPORT="tcp"
                REMOTE_HOST="$2"
                shift 2
                ;;
            --name)
                if [[ "$command" == "ctx" ]]; then
                    CONTEXT_NAME="$2"
                elif [[ "$command" == "buildx" ]]; then
                    BUILDX_NAME="$2"
                fi
                shift 2
                ;;
            --cert-path)
                CERT_PATH="$2"
                shift 2
                ;;
            --skip-verify)
                SKIP_VERIFY="true"
                shift
                ;;
            --remote-socket)
                REMOTE_SOCKET="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            setup|start|stop|restart|remove|status|test|list)
                action="$1"
                shift
                if [[ "$action" == "setup" && $# -gt 0 ]]; then
                    target="$1"
                    shift
                fi
                ;;
            *)
                log_error "Unknown option: $1"
                usage >&2
                exit 1
                ;;
        esac
    done
    
    # Set target if provided
    if [[ -n "$target" ]]; then
        case "$TRANSPORT" in
            ssh)
                SSH_HOST="$target"
                ;;
            tls|tcp)
                REMOTE_HOST="$target"
                ;;
        esac
    fi
    
    # Parse host:port for TLS/TCP
    if [[ "$TRANSPORT" != "ssh" && -n "$REMOTE_HOST" ]]; then
        if [[ "$REMOTE_HOST" == *":"* ]]; then
            local port="${REMOTE_HOST#*:}"
            REMOTE_HOST="${REMOTE_HOST%:*}"
            if [[ "$TRANSPORT" == "tls" ]]; then
                TLS_PORT="$port"
            else
                TCP_PORT="$port"
            fi
        fi
    fi
    
    # Validate action
    if [[ -z "$action" ]]; then
        log_error "Action is required"
        usage >&2
        exit 1
    fi
    
    echo "$command" "$action"
}

# Get configuration file paths
get_config_files() {
    local command="$1"
    local config_file="${CONFIG_DIR}/${command}"
    local env_file="${CONFIG_DIR}/${command}.env"
    
    case "$command" in
        ctx)
            if [[ -n "$CONTEXT_NAME" ]]; then
                config_file="${CONFIG_DIR}/ctx-${CONTEXT_NAME}"
                env_file="${CONFIG_DIR}/ctx-${CONTEXT_NAME}.env"
            fi
            ;;
        buildx)
            if [[ -n "$BUILDX_NAME" ]]; then
                config_file="${CONFIG_DIR}/buildx-${BUILDX_NAME}"
                env_file="${CONFIG_DIR}/buildx-${BUILDX_NAME}.env"
            fi
            ;;
    esac
    
    echo "$config_file" "$env_file"
}

# Get unique socket path for SSH connections
get_ssh_socket_path() {
    local command="$1"
    local identifier="$command"
    
    case "$command" in
        ctx)
            if [[ -n "$CONTEXT_NAME" ]]; then
                identifier="ctx-${CONTEXT_NAME}"
            fi
            ;;
        buildx)
            if [[ -n "$BUILDX_NAME" ]]; then
                identifier="buildx-${BUILDX_NAME}"
            fi
            ;;
    esac
    
    echo "/tmp/docker-${identifier}-${SSH_HOST}.sock"
}

# Generate configuration
generate_config() {
    local command="$1"
    
    cat << EOF
# Docker $command configuration
TRANSPORT="$TRANSPORT"
EOF
    
    case "$TRANSPORT" in
        ssh)
            cat << EOF
SSH_HOST="$SSH_HOST"
LOCAL_SOCKET="$LOCAL_SOCKET"
REMOTE_SOCKET="$REMOTE_SOCKET"
EOF
            ;;
        tls)
            cat << EOF
REMOTE_HOST="$REMOTE_HOST"
TLS_PORT="$TLS_PORT"
SKIP_VERIFY="$SKIP_VERIFY"
CERT_PATH="$CERT_PATH"
EOF
            ;;
        tcp)
            cat << EOF
REMOTE_HOST="$REMOTE_HOST"
TCP_PORT="$TCP_PORT"
EOF
            ;;
    esac
    
    case "$command" in
        ctx)
            [[ -n "$CONTEXT_NAME" ]] && echo "CONTEXT_NAME=\"$CONTEXT_NAME\""
            ;;
        buildx)
            [[ -n "$BUILDX_NAME" ]] && echo "BUILDX_NAME=\"$BUILDX_NAME\""
            ;;
    esac
}

# Generate environment configuration
generate_env() {
    case "$TRANSPORT" in
        ssh)
            cat << EOF
export DOCKER_HOST="unix://$LOCAL_SOCKET"
unset DOCKER_TLS_VERIFY
unset DOCKER_CERT_PATH
EOF
            ;;
        tls)
            cat << EOF
export DOCKER_HOST="tcp://$REMOTE_HOST:$TLS_PORT"
EOF
            if [[ "$SKIP_VERIFY" == "true" ]]; then
                echo "unset DOCKER_TLS_VERIFY"
            else
                echo "export DOCKER_TLS_VERIFY=\"1\""
            fi
            
            if [[ -n "$CERT_PATH" ]]; then
                echo "export DOCKER_CERT_PATH=\"$CERT_PATH\""
            else
                echo "unset DOCKER_CERT_PATH"
            fi
            ;;
        tcp)
            cat << EOF
export DOCKER_HOST="tcp://$REMOTE_HOST:$TCP_PORT"
unset DOCKER_TLS_VERIFY
unset DOCKER_CERT_PATH
EOF
            ;;
    esac
}

# Load configuration
load_config() {
    local command="$1"
    local config_file env_file
    read -r config_file env_file < <(get_config_files "$command")
    
    if [[ -f "$config_file" ]]; then
        # shellcheck source=/dev/null
        source "$config_file"
        
        # Update socket path for SSH
        if [[ "$TRANSPORT" == "ssh" ]]; then
            LOCAL_SOCKET=$(get_ssh_socket_path "$command")
        fi
        
        return 0
    else
        log_error "No configuration found at $config_file"
        return 1
    fi
}

# Save configuration
save_config() {
    local command="$1"
    local config_file env_file
    read -r config_file env_file < <(get_config_files "$command")
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    
    # Set socket path for SSH
    if [[ "$TRANSPORT" == "ssh" ]]; then
        LOCAL_SOCKET=$(get_ssh_socket_path "$command")
        mkdir -p "$SSH_CONTROL_DIR"
    fi
    
    # Save configuration
    generate_config "$command" > "$config_file"
    generate_env > "$env_file"
    
    log_success "Configuration saved to $config_file"
    log_success "Environment saved to $env_file"
}

# Test SSH connection
test_ssh_connection() {
    log_info "Testing SSH connection to $SSH_HOST..."
    
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_HOST" "echo 'SSH connection successful'" >/dev/null 2>&1; then
        log_success "SSH connection successful"
        return 0
    else
        log_error "SSH connection failed"
        log_info "Please ensure:"
        log_info "  - SSH host '$SSH_HOST' is configured in ~/.ssh/config"
        log_info "  - SSH key authentication is set up"
        log_info "  - Host is reachable and SSH server is running"
        return 1
    fi
}

# Test Docker on remote host via SSH
test_remote_docker_ssh() {
    log_info "Testing Docker access on remote host..."
    
    local docker_test_cmd="test -S $REMOTE_SOCKET && docker version >/dev/null 2>&1"
    
    if ssh "$SSH_HOST" "$docker_test_cmd" >/dev/null 2>&1; then
        log_success "Docker is accessible on remote host"
        return 0
    else
        log_error "Docker is not accessible on remote host"
        log_info "Please ensure:"
        log_info "  - Docker is installed and running"
        log_info "  - Remote user is in the 'docker' group"
        log_info "  - Docker socket exists at $REMOTE_SOCKET"
        return 1
    fi
}

# Test Docker via TLS/TCP
test_remote_docker_direct() {
    log_info "Testing Docker access via $TRANSPORT..."
    
    local docker_host
    if [[ "$TRANSPORT" == "tls" ]]; then
        docker_host="tcp://$REMOTE_HOST:$TLS_PORT"
    else
        docker_host="tcp://$REMOTE_HOST:$TCP_PORT"
    fi
    
    # Backup environment
    local old_docker_host="$DOCKER_HOST"
    local old_tls_verify="$DOCKER_TLS_VERIFY"
    local old_cert_path="$DOCKER_CERT_PATH"
    
    # Set test environment
    export DOCKER_HOST="$docker_host"
    
    if [[ "$TRANSPORT" == "tls" ]]; then
        if [[ "$SKIP_VERIFY" == "true" ]]; then
            unset DOCKER_TLS_VERIFY
        else
            export DOCKER_TLS_VERIFY="1"
        fi
        
        if [[ -n "$CERT_PATH" ]]; then
            export DOCKER_CERT_PATH="$CERT_PATH"
        fi
    else
        unset DOCKER_TLS_VERIFY
        unset DOCKER_CERT_PATH
    fi
    
    # Test connection
    local result=0
    if docker version >/dev/null 2>&1; then
        log_success "Docker is accessible via $TRANSPORT"
    else
        log_error "Docker is not accessible via $TRANSPORT"
        result=1
    fi
    
    # Restore environment
    [[ -n "$old_docker_host" ]] && export DOCKER_HOST="$old_docker_host" || unset DOCKER_HOST
    [[ -n "$old_tls_verify" ]] && export DOCKER_TLS_VERIFY="$old_tls_verify" || unset DOCKER_TLS_VERIFY
    [[ -n "$old_cert_path" ]] && export DOCKER_CERT_PATH="$old_cert_path" || unset DOCKER_CERT_PATH
    
    return $result
}

# Start SSH tunnel
start_ssh_tunnel() {
    local command="$1"
    
    if [[ -S "$LOCAL_SOCKET" ]]; then
        log_info "SSH tunnel already exists"
        return 0
    fi
    
    log_info "Starting SSH tunnel to $SSH_HOST..."
    
    # Ensure local socket directory exists
    mkdir -p "$(dirname "$LOCAL_SOCKET")"
    
    # Start SSH tunnel
    local control_socket="${SSH_CONTROL_DIR}/docker-${SSH_HOST}"
    local ssh_args=(
        "-o" "ControlMaster=auto"
        "-o" "ControlPath=$control_socket"
        "-o" "ControlPersist=600"
        "-o" "ExitOnForwardFailure=yes"
        "-o" "ServerAliveInterval=30"
        "-o" "ServerAliveCountMax=3"
        "-L" "$LOCAL_SOCKET:$REMOTE_SOCKET"
        "-N"
        "-f"
    )
    
    if ssh "${ssh_args[@]}" "$SSH_HOST"; then
        sleep 2
        if [[ -S "$LOCAL_SOCKET" ]]; then
            log_success "SSH tunnel started successfully"
            return 0
        else
            log_error "SSH tunnel started but socket not available"
            return 1
        fi
    else
        log_error "Failed to start SSH tunnel"
        return 1
    fi
}

# Stop SSH tunnel
stop_ssh_tunnel() {
    local command="$1"
    
    if [[ ! -S "$LOCAL_SOCKET" ]]; then
        log_info "SSH tunnel not running"
        return 0
    fi
    
    log_info "Stopping SSH tunnel..."
    
    # Find and kill SSH process
    local pid
    pid=$(pgrep -f "ssh.*${SSH_HOST}.*${LOCAL_SOCKET}" 2>/dev/null | head -1)
    
    if [[ -n "$pid" ]]; then
        if kill "$pid" 2>/dev/null; then
            # Wait for graceful termination
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
            done
            
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
        fi
    fi
    
    # Clean up socket
    if [[ -S "$LOCAL_SOCKET" ]]; then
        rm -f "$LOCAL_SOCKET"
    fi
    
    log_success "SSH tunnel stopped"
}

# Check if connection is active
is_connection_active() {
    local command="$1"
    
    load_config "$command" || return 1
    
    case "$TRANSPORT" in
        ssh)
            if [[ -S "$LOCAL_SOCKET" ]]; then
                local old_docker_host="$DOCKER_HOST"
                export DOCKER_HOST="unix://$LOCAL_SOCKET"
                if docker version >/dev/null 2>&1; then
                    [[ -n "$old_docker_host" ]] && export DOCKER_HOST="$old_docker_host" || unset DOCKER_HOST
                    return 0
                fi
                [[ -n "$old_docker_host" ]] && export DOCKER_HOST="$old_docker_host" || unset DOCKER_HOST
            fi
            return 1
            ;;
        tls|tcp)
            test_remote_docker_direct >/dev/null 2>&1
            ;;
    esac
}

# API Command Functions
api_setup() {
    log_info "Setting up Docker API connection..."
    
    case "$TRANSPORT" in
        ssh)
            if [[ -z "$SSH_HOST" ]]; then
                log_error "SSH host is required"
                return 1
            fi
            test_ssh_connection || return 1
            test_remote_docker_ssh || return 1
            ;;
        tls|tcp)
            if [[ -z "$REMOTE_HOST" ]]; then
                log_error "Remote host is required"
                return 1
            fi
            test_remote_docker_direct || return 1
            ;;
    esac
    
    save_config "api"
    log_success "API connection configured"
}

api_start() {
    load_config "api" || return 1
    
    case "$TRANSPORT" in
        ssh)
            start_ssh_tunnel "api"
            ;;
        tls|tcp)
            log_info "Direct connection - no startup required"
            ;;
    esac
    
    # Output environment for sourcing
    if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
        generate_env
    fi
}

api_stop() {
    load_config "api" || return 1
    
    case "$TRANSPORT" in
        ssh)
            stop_ssh_tunnel "api"
            ;;
        tls|tcp)
            log_info "Direct connection - no shutdown required"
            ;;
    esac
}

api_status() {
    log_info "Docker API Status"
    echo "=================="
    
    if load_config "api"; then
        echo "Transport: $TRANSPORT"
        case "$TRANSPORT" in
            ssh)
                echo "SSH Host: $SSH_HOST"
                echo "Local Socket: $LOCAL_SOCKET"
                echo "Remote Socket: $REMOTE_SOCKET"
                ;;
            tls)
                echo "Remote Host: $REMOTE_HOST:$TLS_PORT"
                echo "TLS Verify: $(if [[ "$SKIP_VERIFY" == "true" ]]; then echo "disabled"; else echo "enabled"; fi)"
                echo "Cert Path: ${CERT_PATH:-"(default)"}"
                ;;
            tcp)
                echo "Remote Host: $REMOTE_HOST:$TCP_PORT"
                ;;
        esac
        echo ""
        
        if is_connection_active "api"; then
            log_success "Connection is active"
        else
            log_warning "Connection is not active"
        fi
    else
        log_info "No API configuration found"
    fi
}

api_test() {
    load_config "api" || return 1
    
    case "$TRANSPORT" in
        ssh)
            if [[ ! -S "$LOCAL_SOCKET" ]]; then
                log_error "SSH tunnel not running - start with: $0 api start"
                return 1
            fi
            local old_docker_host="$DOCKER_HOST"
            export DOCKER_HOST="unix://$LOCAL_SOCKET"
            ;;
        tls|tcp)
            test_remote_docker_direct
            return $?
            ;;
    esac
    
    if docker version >/dev/null 2>&1; then
        log_success "Docker API connection successful"
        docker version --format 'Client: {{.Client.Version}}, Server: {{.Server.Version}}'
        [[ -n "$old_docker_host" ]] && export DOCKER_HOST="$old_docker_host" || unset DOCKER_HOST
        return 0
    else
        log_error "Docker API connection failed"
        [[ -n "$old_docker_host" ]] && export DOCKER_HOST="$old_docker_host" || unset DOCKER_HOST
        return 1
    fi
}

api_remove() {
    load_config "api" 2>/dev/null && api_stop
    
    local config_file env_file
    read -r config_file env_file < <(get_config_files "api")
    
    [[ -f "$config_file" ]] && rm "$config_file" && log_success "Removed $config_file"
    [[ -f "$env_file" ]] && rm "$env_file" && log_success "Removed $env_file"
    
    log_info "To reset environment: unset DOCKER_HOST DOCKER_TLS_VERIFY DOCKER_CERT_PATH"
}

# Context Command Functions
ctx_setup() {
    log_info "Setting up Docker context..."
    
    if [[ -z "$CONTEXT_NAME" ]]; then
        CONTEXT_NAME="remote-$(echo "$SSH_HOST$REMOTE_HOST" | tr '.:' '-')"
        log_info "Using context name: $CONTEXT_NAME"
    fi
    
    case "$TRANSPORT" in
        ssh)
            test_ssh_connection || return 1
            test_remote_docker_ssh || return 1
            ;;
        tls|tcp)
            test_remote_docker_direct || return 1
            ;;
    esac
    
    save_config "ctx"
    log_success "Context configured: $CONTEXT_NAME"
}

ctx_start() {
    load_config "ctx" || return 1
    
    case "$TRANSPORT" in
        ssh)
            start_ssh_tunnel "ctx" || return 1
            ;;
    esac
    
    # Create Docker context
    local endpoint
    case "$TRANSPORT" in
        ssh)
            endpoint="unix://$LOCAL_SOCKET"
            ;;
        tls)
            endpoint="tcp://$REMOTE_HOST:$TLS_PORT"
            ;;
        tcp)
            endpoint="tcp://$REMOTE_HOST:$TCP_PORT"
            ;;
    esac
    
    local context_args=("--docker" "host=$endpoint")
    
    if [[ "$TRANSPORT" == "tls" && "$SKIP_VERIFY" != "true" && -n "$CERT_PATH" ]]; then
        context_args+=("--docker" "ca=$CERT_PATH/ca.pem")
        context_args+=("--docker" "cert=$CERT_PATH/cert.pem")
        context_args+=("--docker" "key=$CERT_PATH/key.pem")
    fi
    
    if docker context create "$CONTEXT_NAME" "${context_args[@]}" >/dev/null 2>&1; then
        log_success "Docker context '$CONTEXT_NAME' created"
        log_info "Use with: docker --context $CONTEXT_NAME <command>"
    else
        log_warning "Context may already exist or creation failed"
    fi
}

ctx_stop() {
    load_config "ctx" || return 1
    
    # Remove Docker context
    if docker context rm "$CONTEXT_NAME" >/dev/null 2>&1; then
        log_success "Docker context '$CONTEXT_NAME' removed"
    fi
    
    case "$TRANSPORT" in
        ssh)
            stop_ssh_tunnel "ctx"
            ;;
    esac
}

ctx_status() {
    log_info "Docker Context Status"
    echo "====================="
    
    if load_config "ctx"; then
        echo "Context Name: $CONTEXT_NAME"
        echo "Transport: $TRANSPORT"
        echo ""
        
        if docker context ls --format "table {{.Name}}\t{{.DockerEndpoint}}" | grep -q "^$CONTEXT_NAME"; then
            log_success "Context exists"
            docker context ls | grep "$CONTEXT_NAME"
        else
            log_warning "Context not found"
        fi
    else
        log_info "No context configuration found"
    fi
}

ctx_list() {
    log_info "Docker Contexts"
    echo "==============="
    docker context ls
}

ctx_remove() {
    load_config "ctx" 2>/dev/null && ctx_stop
    
    local config_file env_file
    read -r config_file env_file < <(get_config_files "ctx")
    
    [[ -f "$config_file" ]] && rm "$config_file" && log_success "Removed $config_file"
    [[ -f "$env_file" ]] && rm "$env_file" && log_success "Removed $env_file"
}

# Buildx Command Functions
buildx_setup() {
    log_info "Setting up Docker buildx builder..."
    
    if [[ -z "$BUILDX_NAME" ]]; then
        BUILDX_NAME="remote-$(echo "$SSH_HOST$REMOTE_HOST" | tr '.:' '-')"
        log_info "Using builder name: $BUILDX_NAME"
    fi
    
    case "$TRANSPORT" in
        ssh)
            test_ssh_connection || return 1
            test_remote_docker_ssh || return 1
            ;;
        tls|tcp)
            test_remote_docker_direct || return 1
            ;;
    esac
    
    save_config "buildx"
    log_success "Buildx builder configured: $BUILDX_NAME"
}

buildx_start() {
    load_config "buildx" || return 1
    
    case "$TRANSPORT" in
        ssh)
            start_ssh_tunnel "buildx" || return 1
            ;;
    esac
    
    # Create buildx builder
    local endpoint
    case "$TRANSPORT" in
        ssh)
            endpoint="unix://$LOCAL_SOCKET"
            ;;
        tls)
            endpoint="tcp://$REMOTE_HOST:$TLS_PORT"
            ;;
        tcp)
            endpoint="tcp://$REMOTE_HOST:$TCP_PORT"
            ;;
    esac
    
    local builder_args=("--name" "$BUILDX_NAME" "--driver" "docker")
    
    if [[ "$TRANSPORT" == "tls" && "$SKIP_VERIFY" != "true" ]]; then
        builder_args+=("--driver-opt" "env.DOCKER_TLS_VERIFY=1")
        [[ -n "$CERT_PATH" ]] && builder_args+=("--driver-opt" "env.DOCKER_CERT_PATH=$CERT_PATH")
    fi
    
    builder_args+=("$endpoint")
    
    if docker buildx create "${builder_args[@]}" >/dev/null 2>&1; then
        log_success "Buildx builder '$BUILDX_NAME' created"
        log_info "Use with: docker buildx build --builder $BUILDX_NAME <args>"
    else
        log_warning "Builder may already exist or creation failed"
    fi
}

buildx_stop() {
    load_config "buildx" || return 1
    
    # Remove buildx builder
    if docker buildx rm "$BUILDX_NAME" >/dev/null 2>&1; then
        log_success "Buildx builder '$BUILDX_NAME' removed"
    fi
    
    case "$TRANSPORT" in
        ssh)
            stop_ssh_tunnel "buildx"
            ;;
    esac
}

buildx_status() {
    log_info "Docker Buildx Status"
    echo "===================="
    
    if load_config "buildx"; then
        echo "Builder Name: $BUILDX_NAME"
        echo "Transport: $TRANSPORT"
        echo ""
        
        if docker buildx ls | grep -q "$BUILDX_NAME"; then
            log_success "Builder exists"
            docker buildx ls | grep "$BUILDX_NAME"
        else
            log_warning "Builder not found"
        fi
    else
        log_info "No buildx configuration found"
    fi
}

buildx_list() {
    log_info "Docker Buildx Builders"
    echo "======================"
    docker buildx ls
}

buildx_remove() {
    load_config "buildx" 2>/dev/null && buildx_stop
    
    local config_file env_file
    read -r config_file env_file < <(get_config_files "buildx")
    
    [[ -f "$config_file" ]] && rm "$config_file" && log_success "Removed $config_file"
    [[ -f "$env_file" ]] && rm "$env_file" && log_success "Removed $env_file"
}

# Main function
main() {
    local command action
    read -r command action < <(parse_args "$@")
    
    case "$command" in
        api)
            case "$action" in
                setup) api_setup ;;
                start) api_start ;;
                stop) api_stop ;;
                restart) api_stop; sleep 1; api_start ;;
                status) api_status ;;
                test) api_test ;;
                remove) api_remove ;;
                *) log_error "Unknown api action: $action"; exit 1 ;;
            esac
            ;;
        ctx)
            case "$action" in
                setup) ctx_setup ;;
                start) ctx_start ;;
                stop) ctx_stop ;;
                restart) ctx_stop; sleep 1; ctx_start ;;
                status) ctx_status ;;
                test) ctx_start ;;
                list) ctx_list ;;
                remove) ctx_remove ;;
                *) log_error "Unknown ctx action: $action"; exit 1 ;;
            esac
            ;;
        buildx)
            case "$action" in
                setup) buildx_setup ;;
                start) buildx_start ;;
                stop) buildx_stop ;;
                restart) buildx_stop; sleep 1; buildx_start ;;
                status) buildx_status ;;
                test) buildx_start ;;
                list) buildx_list ;;
                remove) buildx_remove ;;
                *) log_error "Unknown buildx action: $action"; exit 1 ;;
            esac
            ;;
    esac
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi