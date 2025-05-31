# Integration Guide

This guide shows how to integrate dev-env into existing projects, CI/CD pipelines, and development workflows.

## Project Integration

### Adding dev-env to Existing Projects

#### 1. Basic Integration

Add dev-env configuration to your project root:

```python
# dev-env.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="myproject",
    base_image="python:3.13",
    git=GitConfig(
        url="git@github.com:organization/myproject.git"
    ),
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="myproject-cache",
            target="/root/.cache",
            type="named"
        )
    ]
)
```

Add to your README:
```markdown
## Development Environment

This project uses dev-env for containerized development.

### Quick Start
```bash
# Install dev-env
pip install dev-env

# Start development environment
dev-env up dev-env.py

# Connect via SSH
dev-env ssh myproject
```

#### 2. Multiple Environment Support

Create environment configurations for different stages:

```
project/
├── dev-env/
│   ├── development.py
│   ├── testing.py
│   └── staging.py
├── src/
└── README.md
```

**development.py:**
```python
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="myproject-dev",
    base_image="python:3.13",
    git=GitConfig(
        url="git@github.com:org/myproject.git",
        branch="develop"
    ),
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="dev-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "DEBUG": "true",
        "LOG_LEVEL": "debug"
    }
)
```

**testing.py:**
```python
from dev_env.config import Environment, VolumeMount

environment = Environment(
    name="myproject-test",
    base_image="python:3.13",
    command=["pytest", "-v"],
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="test-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "CI": "true",
        "PYTHONPATH": "/app"
    }
)
```

### Project-Specific Scripts

Create convenience scripts in your project:

**scripts/dev-setup.sh:**
```bash
#!/bin/bash
set -e

echo "Setting up development environment..."

# Start environment
dev-env up dev-env/development.py

# Install dependencies
dev-env exec myproject-dev pip install -r requirements.txt
dev-env exec myproject-dev pip install -r requirements-dev.txt

# Run initial setup
dev-env exec myproject-dev python manage.py migrate
dev-env exec myproject-dev python manage.py collectstatic --noinput

echo "✅ Development environment ready!"
echo "Connect with: dev-env ssh myproject-dev"
```

**scripts/run-tests.sh:**
```bash
#!/bin/bash
set -e

echo "Running tests in isolated environment..."

# Start test environment
dev-env up dev-env/testing.py

# Install dependencies
dev-env exec myproject-test pip install -r requirements.txt
dev-env exec myproject-test pip install -r requirements-dev.txt

# Run tests
dev-env exec myproject-test pytest --cov=src --cov-report=html

# Cleanup
dev-env down myproject-test

echo "✅ Tests completed!"
```

Make scripts executable:
```bash
chmod +x scripts/*.sh
```

## CI/CD Integration

### GitHub Actions

#### Basic Integration

```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.13'
    
    - name: Install dev-env
      run: |
        pip install git+https://github.com/org/dev-env.git
    
    - name: Run tests
      run: |
        dev-env up dev-env/testing.py
        dev-env exec myproject-test pytest --cov --junitxml=test-results.xml
        dev-env down myproject-test --volumes
    
    - name: Upload test results
      uses: actions/upload-artifact@v4
      if: always()
      with:
        name: test-results
        path: test-results.xml
```

#### Multi-Environment Testing

```yaml
# .github/workflows/matrix-test.yml
name: Matrix Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12', '3.13']
        environment: ['testing', 'integration']
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dev-env
      run: pip install dev-env
    
    - name: Create environment config
      run: |
        cat > test-config.py << EOF
        from dev_env.config import Environment, VolumeMount
        
        environment = Environment(
            name="test-py${{ matrix.python-version }}",
            base_image="python:${{ matrix.python-version }}",
            volumes=[
                VolumeMount(source=".", target="/app")
            ],
            environment={
                "CI": "true",
                "TEST_TYPE": "${{ matrix.environment }}"
            }
        )
        EOF
    
    - name: Run tests
      run: |
        dev-env up test-config.py
        dev-env exec test-py${{ matrix.python-version }} ./scripts/test-${{ matrix.environment }}.sh
        dev-env down test-py${{ matrix.python-version }} --volumes
```

### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

services:
  - docker:dind

before_script:
  - apt-get update -qq && apt-get install -y python3-pip
  - pip3 install dev-env

test:
  stage: test
  script:
    - dev-env up dev-env/testing.py
    - dev-env exec myproject-test pytest --cov --junitxml=report.xml
    - dev-env down myproject-test --volumes
  artifacts:
    reports:
      junit: report.xml
    expire_in: 1 week

integration-test:
  stage: test
  script:
    - dev-env up dev-env/integration.py
    - dev-env exec myproject-integration ./scripts/integration-tests.sh
    - dev-env down myproject-integration --volumes
  only:
    - main
    - develop
```

### Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any
    
    environment {
        PROJECT_NAME = "myproject"
    }
    
    stages {
        stage('Setup') {
            steps {
                script {
                    sh 'pip install dev-env'
                }
            }
        }
        
        stage('Test') {
            parallel {
                stage('Unit Tests') {
                    steps {
                        sh '''
                            dev-env up dev-env/testing.py
                            dev-env exec ${PROJECT_NAME}-test pytest tests/unit/
                            dev-env down ${PROJECT_NAME}-test --volumes
                        '''
                    }
                }
                
                stage('Integration Tests') {
                    steps {
                        sh '''
                            dev-env up dev-env/integration.py
                            dev-env exec ${PROJECT_NAME}-integration pytest tests/integration/
                            dev-env down ${PROJECT_NAME}-integration --volumes
                        '''
                    }
                }
            }
        }
        
        stage('Build') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    dev-env up dev-env/build.py
                    dev-env exec ${PROJECT_NAME}-build ./scripts/build.sh
                    dev-env down ${PROJECT_NAME}-build --volumes
                '''
            }
        }
    }
    
    post {
        always {
            sh 'dev-env list | grep ${PROJECT_NAME} | awk "{print \\$1}" | xargs -r -I {} dev-env down {} --volumes || true'
        }
    }
}
```

## IDE Integration

### Visual Studio Code

#### Dev Container Integration

Create `.devcontainer/devcontainer.json`:

```json
{
    "name": "Dev-Env Container",
    "dockerFile": "../Dockerfile.devcontainer",
    "forwardPorts": [8000, 5432],
    "postCreateCommand": "pip install -r requirements.txt",
    "extensions": [
        "ms-python.python",
        "ms-python.pylint"
    ],
    "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python"
    }
}
```

#### Dev-Env Bridge Script

Create `.vscode/tasks.json`:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Dev Environment",
            "type": "shell",
            "command": "dev-env",
            "args": ["up", "dev-env.py"],
            "group": "build",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": false,
                "panel": "shared"
            }
        },
        {
            "label": "Stop Dev Environment",
            "type": "shell",
            "command": "dev-env",
            "args": ["down", "myproject"],
            "group": "build"
        },
        {
            "label": "Run Tests",
            "type": "shell",
            "command": "dev-env",
            "args": ["exec", "myproject", "pytest"],
            "group": "test"
        }
    ]
}
```

### PyCharm Integration

Create external tools in PyCharm:

1. **Start Environment**
   - Program: `dev-env`
   - Arguments: `up dev-env.py`
   - Working directory: `$ProjectFileDir$`

2. **SSH into Environment**
   - Program: `dev-env`
   - Arguments: `ssh myproject`
   - Working directory: `$ProjectFileDir$`

3. **Run Tests**
   - Program: `dev-env`
   - Arguments: `exec myproject pytest $FilePath$`
   - Working directory: `$ProjectFileDir$`

## Team Collaboration

### Shared Configuration Templates

Create reusable templates for your organization:

```python
# templates/python_web.py
from dev_env.config import Environment, GitConfig, VolumeMount

def create_python_web_env(
    name: str,
    repo_url: str,
    python_version: str = "3.13",
    port: int = 8000
) -> Environment:
    """Standard Python web application environment"""
    return Environment(
        name=name,
        base_image=f"python:{python_version}",
        git=GitConfig(url=repo_url),
        ports={
            22: {"HostPort": 2222},
            port: {"HostPort": port}
        },
        volumes=[
            VolumeMount(source=".", target="/app"),
            VolumeMount(
                source=f"{name}-pip-cache",
                target="/root/.cache/pip",
                type="named"
            )
        ],
        environment={
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1"
        }
    )

# Usage in project
from templates.python_web import create_python_web_env

environment = create_python_web_env(
    name="myapp",
    repo_url="git@github.com:org/myapp.git",
    port=8000
)
```

### Team Scripts

**scripts/team-setup.sh:**
```bash
#!/bin/bash
set -e

DEVELOPER=${1:-$(whoami)}
PORT_OFFSET=${2:-0}

echo "Setting up environment for developer: $DEVELOPER"

# Create personalized config
cat > dev-env-${DEVELOPER}.py << EOF
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="myproject-${DEVELOPER}",
    base_image="python:3.13",
    git=GitConfig(
        url="git@github.com:org/myproject.git",
        branch="feature/${DEVELOPER}"
    ),
    ports={
        22: {"HostPort": $((2222 + PORT_OFFSET))},
        8000: {"HostPort": $((8000 + PORT_OFFSET))}
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="${DEVELOPER}-workspace",
            target="/app",
            type="named"
        )
    ],
    environment={
        "DEVELOPER": "${DEVELOPER}",
        "DEBUG": "true"
    }
)
EOF

# Start environment
dev-env up dev-env-${DEVELOPER}.py

echo "✅ Environment ready for $DEVELOPER"
echo "Connect with: dev-env ssh myproject-${DEVELOPER}"
echo "Access at: http://localhost:$((8000 + PORT_OFFSET))"
```

## Docker Compose Migration

### Converting from Docker Compose

**Original docker-compose.yml:**
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - pip-cache:/root/.cache/pip
    environment:
      - DEBUG=true
    depends_on:
      - db
  
  db:
    image: postgres:16
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass

volumes:
  pip-cache:
  postgres-data:
```

**Converted dev-env configuration:**
```python
# dev-env.py
from dev_env.config import Environment, GitConfig, VolumeMount, NetworkConfig

# Shared network
app_network = NetworkConfig(name="myapp-network")

# Database
db = Environment(
    name="myapp-db",
    base_image="postgres:16",
    network=app_network,
    ports={
        5432: {"HostPort": 5432}
    },
    volumes=[
        VolumeMount(
            source="postgres-data",
            target="/var/lib/postgresql/data",
            type="named"
        )
    ],
    environment={
        "POSTGRES_DB": "myapp",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "pass"
    }
)

# Web application
web = Environment(
    name="myapp-web",
    base_image="python:3.13",
    network=app_network,
    git=GitConfig(
        url="git@github.com:org/myapp.git"
    ),
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source=".", target="/app"),
        VolumeMount(
            source="pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "DEBUG": "true",
        "DATABASE_URL": "postgresql://user:pass@myapp-db:5432/myapp"
    }
)

environments = {
    "db": db,
    "web": web
}
```

**Migration workflow:**
```bash
# Stop docker-compose services
docker-compose down

# Start dev-env services
dev-env up dev-env.py --name myapp-db
dev-env up dev-env.py --name myapp-web

# Migrate data (if needed)
dev-env exec myapp-db pg_restore /backups/data.sql
```

## API Integration

### Programmatic Usage

```python
# automation/deploy.py
from dev_env.config import Environment, load_environment
from dev_env.docker import DockerClient
from dev_env.state import StateManager

def deploy_environment(config_path: str, env_name: str) -> bool:
    """Deploy environment programmatically"""
    try:
        # Load configuration
        env = load_environment(config_path)
        
        # Initialize Docker client
        docker = DockerClient()
        
        # Initialize state manager
        state = StateManager()
        
        # Create and start environment
        container_id = docker.create_container(env)
        docker.start_container(container_id)
        
        # Track in state
        state.add_environment(env_name, container_id, config_path)
        
        return True
    except Exception as e:
        print(f"Deployment failed: {e}")
        return False

# Usage
if deploy_environment("prod-config.py", "production"):
    print("✅ Production environment deployed")
else:
    print("❌ Deployment failed")
```

### REST API Wrapper

```python
# api/dev_env_api.py
from flask import Flask, request, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route('/environments', methods=['GET'])
def list_environments():
    """List all environments"""
    result = subprocess.run(['dev-env', 'list'], capture_output=True, text=True)
    if result.returncode == 0:
        return jsonify({"environments": result.stdout.split('\n')})
    return jsonify({"error": result.stderr}), 500

@app.route('/environments', methods=['POST'])
def create_environment():
    """Create new environment"""
    data = request.get_json()
    config_file = data.get('config_file')
    name = data.get('name')
    
    cmd = ['dev-env', 'up', config_file]
    if name:
        cmd.extend(['--name', name])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return jsonify({"status": "created", "output": result.stdout})
    return jsonify({"error": result.stderr}), 500

@app.route('/environments/<name>', methods=['DELETE'])
def delete_environment(name):
    """Delete environment"""
    result = subprocess.run(
        ['dev-env', 'down', name, '--volumes'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        return jsonify({"status": "deleted"})
    return jsonify({"error": result.stderr}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

## Monitoring Integration

### Prometheus Metrics

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import subprocess
import json
import time

# Metrics
environments_total = Gauge('dev_env_environments_total', 'Total number of environments')
environment_creation_time = Histogram('dev_env_creation_seconds', 'Time to create environment')
environment_failures = Counter('dev_env_failures_total', 'Failed environment operations')

def collect_metrics():
    """Collect dev-env metrics"""
    try:
        # Get environment count
        result = subprocess.run(['dev-env', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            count = len([line for line in result.stdout.split('\n') if line.strip()])
            environments_total.set(count)
    except Exception as e:
        environment_failures.inc()

if __name__ == '__main__':
    # Start metrics server
    start_http_server(8001)
    
    # Collect metrics every 30 seconds
    while True:
        collect_metrics()
        time.sleep(30)
```

### Logging Integration

```python
# monitoring/logging_config.py
import logging
import json
import subprocess
from datetime import datetime

class DevEnvHandler(logging.Handler):
    """Custom log handler for dev-env operations"""
    
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module
        }
        
        # Log to centralized system
        # (e.g., ELK stack, Splunk, etc.)
        print(json.dumps(log_entry))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('dev-env-integration')
logger.addHandler(DevEnvHandler())

def log_environment_operation(operation: str, env_name: str, success: bool):
    """Log environment operations"""
    if success:
        logger.info(f"Environment {operation} successful", extra={
            'operation': operation,
            'environment': env_name,
            'success': True
        })
    else:
        logger.error(f"Environment {operation} failed", extra={
            'operation': operation,
            'environment': env_name,
            'success': False
        })
```

This integration guide provides comprehensive examples for incorporating dev-env into various development workflows, CI/CD systems, and team environments. For more technical details, see the [API Reference](api-reference.md).