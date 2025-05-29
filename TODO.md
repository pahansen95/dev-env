# dev-env: Implementation Roadmap

## 🚧 Critical Path - Container Initialization Pipeline

### 1. Docker Exec API (Blocks Everything)
- [ ] Implement `create_exec` endpoint in `docker.py`
- [ ] Implement `start_exec` with output capture
- [ ] Add streaming response handler for real-time output
- [ ] Test exec functionality with basic commands

### 2. SSH Server Setup
- [ ] Auto-install OpenSSH server in containers
- [ ] Generate ephemeral host keys on startup
- [ ] Inject host's public key as authorized_keys
- [ ] Configure and start SSH daemon
- [ ] Validate SSH connectivity

### 3. Git Repository Integration  
- [ ] Clone repositories inside containers via exec
- [ ] Configure git identity from host settings
- [ ] Handle authentication (SSH agent forwarding)
- [ ] Support shallow clones for performance

### 4. Image Pull Support
- [ ] Implement streaming pull with progress
- [ ] Parse image specifications (registry/name:tag)
- [ ] Handle authentication for private registries
- [ ] Add progress callback mechanism

### 5. Complete Initialization Flow
- [ ] Integrate all components in `cmd_up`
- [ ] Add health checks before declaring "ready"
- [ ] Implement proper error handling with rollback
- [ ] Show connection instructions on success

## 📋 Core Functionality

### Container Management
- [ ] Implement `exec` command functionality
- [ ] Add container health monitoring
- [ ] Support attach/detach operations
- [ ] Add `logs` command for debugging

### Developer Experience
- [ ] Progress indicators for long operations
- [ ] Actionable error messages with remediation
- [ ] Shell completion scripts
- [ ] Quick-start wizard for new users

### Networking & Volumes
- [ ] Validate port mappings before creation
- [ ] Support custom networks
- [ ] Implement bind mount validation
- [ ] Add volume size tracking

## 🧪 Testing & Validation

### Integration Tests
- [ ] Test complete environment lifecycle
- [ ] Verify SSH access works
- [ ] Validate Git cloning
- [ ] Test state persistence across restarts

### Error Scenarios
- [ ] Handle missing Docker daemon gracefully
- [ ] Test cleanup on initialization failure
- [ ] Verify port conflict detection
- [ ] Test image pull failures

## 📚 Documentation

### User Documentation
- [ ] Quick start guide
- [ ] Common workflows and examples
- [ ] Troubleshooting guide
- [ ] Migration from docker-compose

### Developer Documentation
- [ ] Architecture deep dive
- [ ] Extension points
- [ ] Contributing guidelines
- [ ] API reference

## 🚀 Future Enhancements

### Multi-Container Support
- [ ] Environment dependency management
- [ ] Shared networks between environments
- [ ] Service discovery mechanism
- [ ] Environment composition

### Advanced Features
- [ ] Environment templates marketplace
- [ ] Cloud backend support
- [ ] Team collaboration features
- [ ] Resource usage monitoring

### Distribution
- [ ] Package for PyPI
- [ ] Single-file distribution option
- [ ] Homebrew formula
- [ ] Container image with dev-env pre-installed

## Implementation Notes

### Docker Exec Implementation
```python
# Required endpoints:
# POST /containers/{id}/exec - Create exec instance
# POST /exec/{id}/start - Start exec and stream output
# GET /exec/{id}/json - Get exit code
```

### SSH Setup Sequence
1. Check if SSH server installed
2. Install if missing (apt/yum based on image)
3. Generate host keys
4. Create .ssh directory
5. Copy authorized_keys
6. Start sshd daemon

### Git Clone Strategy
- Use exec to run git inside container
- Mount SSH socket for authentication
- Configure user.name/user.email from host
- Support both HTTPS and SSH URLs

---

## ✅ Completed Work

### Phase 1: Core Infrastructure
- [x] Docker client using `http.client` and Unix sockets
- [x] Minimal Docker API wrapper for container operations
- [x] Container creation and lifecycle management
- [x] Volume creation support

### Phase 2: Configuration System
- [x] Configuration system using `dataclasses` instead of Pydantic
- [x] Python-based configuration files
- [x] JSON configuration support
- [x] Environment templates (Python, Node, Ubuntu)
- [x] Configuration validation with post_init

### Phase 3: State Management
- [x] State management using `sqlite3`
- [x] Atomic operations with transactions
- [x] Environment tracking and persistence
- [x] Metadata storage capability

### Phase 4: CLI Implementation
- [x] CLI using `argparse` instead of Click
- [x] Basic commands: up, down, list
- [x] SSH command with port detection
- [x] State directory management

### Phase 5: Utilities
- [x] Docker availability checking
- [x] Container name generation
- [x] Git/SSH operation utilities
- [x] Port mapping parser
- [x] Configuration hashing

### Phase 6: Project Setup
- [x] Project structure created
- [x] `pyproject.toml` configured with zero dependencies
- [x] Entry point defined
- [x] `__main__.py` for direct module execution
- [x] Example configurations (Python, Node, Ubuntu)
- [x] Architecture documentation in README
- [x] Implementation strategy documented