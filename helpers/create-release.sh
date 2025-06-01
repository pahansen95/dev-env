#!/bin/bash
# create-release.sh - Create a validated release tag
# Ensures all validation passes before creating a git tag

set -euo pipefail

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Source utilities
# shellcheck source=./utils.sh
source "${SCRIPT_DIR}/utils.sh"

# Parse command line arguments
VERSION=""
PUSH_TAG=false

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -v, --version VERSION    Specify version (otherwise uses current package version)"
    echo "  -p, --push              Push tag to origin after creation"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Create tag for current version"
    echo "  $0 --push               # Create and push tag"
    echo "  $0 -v 1.2.3            # Create tag for specific version"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -p|--push)
            PUSH_TAG=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

main() {
    log_info "Starting release process"
    
    # Change to project root
    cd "$(get_project_root)"
    
    # Get current package version if not specified
    if [[ -z "$VERSION" ]]; then
        VERSION=$(get_python_version "src/dev_env/__init__.py") || {
            log_error "Failed to get package version"
            exit 1
        }
    fi
    
    # Ensure version doesn't have 'v' prefix (we'll add it for the tag)
    VERSION="${VERSION#v}"
    
    local TAG_NAME="v${VERSION}"
    
    log_info "Preparing release for version: ${VERSION}"
    
    # Check if tag already exists
    if git rev-parse "refs/tags/${TAG_NAME}" >/dev/null 2>&1; then
        log_error "Tag ${TAG_NAME} already exists"
        exit 1
    fi
    
    # Run validation (without tag mode since tag doesn't exist yet)
    log_progress "Running package validation"
    if ! "${SCRIPT_DIR}/validate-package.sh"; then
        log_error "Package validation failed"
        log_info "Fix the issues above and try again"
        exit 1
    fi
    
    # Create the tag
    log_progress "Creating tag ${TAG_NAME}"
    git tag -a "${TAG_NAME}" -m "Release ${VERSION}" || {
        log_error "Failed to create tag"
        exit 1
    }
    
    log_success "Tag ${TAG_NAME} created successfully"
    
    # Push tag if requested
    if [[ "$PUSH_TAG" == "true" ]]; then
        log_progress "Pushing tag to origin"
        git push origin "${TAG_NAME}" || {
            log_error "Failed to push tag"
            log_info "You can push manually with: git push origin ${TAG_NAME}"
            exit 1
        }
        log_success "Tag pushed to origin"
    else
        log_info "To push this tag: git push origin ${TAG_NAME}"
    fi
    
    log_success "Release ${VERSION} completed!"
}

main "$@"