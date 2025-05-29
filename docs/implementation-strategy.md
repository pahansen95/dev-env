# Implementation Strategy: stdlib-first dev-env

## Overview

Build dev-env using Python standard library exclusively, ensuring zero external dependencies for core functionality.

## Core Principles

1. **Stdlib First**: Use only Python standard library modules
2. **Simple Design**: Minimize complexity, maximize clarity  
3. **Extensible**: Clear points for future enhancements
4. **Pragmatic**: Working code over perfect abstractions

## Architecture

```
src/dev_env/
├── __init__.py
├── cli.py          # argparse-based CLI
├── docker.py       # Minimal Docker client
├── config.py       # Environment configuration
├── state.py        # SQLite persistence
└── utils.py        # Shared utilities
```

## Module Breakdown

### 1. CLI Module (cli.py)
- **stdlib**: `argparse`, `sys`
- **Commands**: up, down, list, exec, ssh
- **Simple argument parsing with help text**

### 2. Docker Module (docker.py)
- **stdlib**: `http.client`, `socket`, `json`
- **Unix socket support for Docker API**
- **Minimal API wrapper for essential operations**

### 3. Config Module (config.py)
- **stdlib**: `dataclasses`, `json`, `pathlib`
- **Environment configuration as Python files**
- **Simple validation using post_init**

### 4. State Module (state.py)
- **stdlib**: `sqlite3`, `contextlib`
- **Track environments and containers**
- **Atomic operations with transactions**

### 5. Utils Module (utils.py)
- **stdlib**: `subprocess`, `shutil`, `tempfile`
- **Git operations via subprocess**
- **SSH key handling and connections**

## Implementation Plan

### Phase 1: MVP (Week 1)
1. Basic Docker client for container lifecycle
2. Simple CLI with up/down commands
3. JSON-based configuration
4. SQLite state tracking

### Phase 2: Core Features (Week 2)
1. Git repository cloning
2. SSH access to containers
3. Volume management
4. Environment listing

### Phase 3: Polish (Week 3)
1. Error handling and recovery
2. Progress indicators
3. Configuration validation
4. Basic test suite

## Key Design Decisions

### Why No External Dependencies?

1. **Portability**: Works anywhere Python is installed
2. **Security**: No supply chain vulnerabilities
3. **Simplicity**: No version conflicts or pip issues
4. **Size**: ~50KB instead of ~2MB with dependencies

### Trade-offs Accepted

1. More verbose code (argparse vs click)
2. Manual HTTP handling (no requests library)
3. Basic formatting (no rich output)
4. Simple validation (no pydantic)

### Future Extension Points

If needed, these can be added as optional dependencies:
- Rich: Enhanced terminal output
- Click: More sophisticated CLI
- Pydantic: Complex configuration validation
- Docker SDK: Advanced Docker features

## Example Code Structure

```python
# src/dev_env/docker.py
import json
import socket
import http.client
from typing import Dict, Any

class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, unix_socket):
        super().__init__('localhost')
        self.unix_socket = unix_socket
    
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.unix_socket)

class DockerClient:
    def __init__(self, socket_path="/var/run/docker.sock"):
        self.socket_path = socket_path
    
    def request(self, method: str, path: str, data: Dict = None) -> Any:
        conn = UnixHTTPConnection(self.socket_path)
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data) if data else None
        
        conn.request(method, path, body, headers)
        response = conn.getresponse()
        result = response.read().decode()
        
        if response.status >= 400:
            raise RuntimeError(f"Docker API error: {response.status}")
        
        return json.loads(result) if result else {}
```

## Success Metrics

1. **Zero runtime dependencies**
2. **< 1000 lines of code for MVP**
3. **< 5 second environment startup**
4. **Works on Python 3.8+**
5. **Single file distribution possible**

## Next Steps

1. Create initial project structure
2. Implement minimal Docker client
3. Build CLI with up/down commands
4. Add state persistence
5. Test on real use cases