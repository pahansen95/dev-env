# Development Workflows

This guide demonstrates common development workflows using dev-env for different languages and project types.

## Python Development

### Basic Python Project

```python
# python-basic.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="python-app",
    base_image="python:3.13-slim",
    git=GitConfig(
        url="https://github.com/username/python-app.git"
    ),
    ports={
        22: {"HostPort": 2222}
    },
    volumes=[
        # Persist pip cache
        VolumeMount(
            source="python-app-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1"
    }
)
```

**Workflow:**
```bash
# Start environment
dev-env up python-basic.py

# Enter environment and set up
dev-env ssh python-app
cd /workspace
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Development cycle
python src/main.py
pytest tests/
```

### Django Web Application

```python
# django-dev.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="django-app",
    base_image="python:3.13",
    git=GitConfig(
        url="git@github.com:organization/django-app.git",
        branch="develop"
    ),
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000},  # Django dev server
        5432: {"HostPort": 5433}   # PostgreSQL (if using docker-in-docker)
    },
    volumes=[
        # Code directory for hot reload
        VolumeMount(source=".", target="/app"),
        # Persist pip packages
        VolumeMount(
            source="django-pip-cache",
            target="/root/.cache/pip",
            type="named"
        ),
        # Django media files
        VolumeMount(
            source="django-media",
            target="/app/media",
            type="named"
        )
    ],
    environment={
        "PYTHONUNBUFFERED": "1",
        "DJANGO_SETTINGS_MODULE": "myproject.settings.dev",
        "DJANGO_DEBUG": "True",
        "DATABASE_URL": "postgresql://user:pass@localhost:5432/myapp"
    }
)
```

**Workflow:**
```bash
# Initial setup
dev-env up django-dev.py
dev-env ssh django-app

# Inside container
cd /app
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000

# Access at http://localhost:8000
# Hot reload works with bind-mounted source
```

### FastAPI Microservice

```python
# fastapi-dev.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="fastapi-service",
    base_image="python:3.13-slim",
    command=["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"],
    working_dir="/app",
    git=GitConfig(
        url="git@github.com:team/fastapi-service.git"
    ),
    ports={
        22: {"HostPort": 2222},
        8000: {"HostPort": 8000}
    },
    volumes=[
        VolumeMount(source="./src", target="/app"),
        VolumeMount(
            source="fastapi-pip-cache",
            target="/root/.cache/pip",
            type="named"
        )
    ],
    environment={
        "PYTHONPATH": "/app",
        "ENVIRONMENT": "development"
    }
)
```

## Node.js Development

### React Application

```python
# react-app.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="react-app",
    base_image="node:20-alpine",
    git=GitConfig(
        url="https://github.com/username/react-app.git"
    ),
    ports={
        22: {"HostPort": 2223},
        3000: {"HostPort": 3000}  # React dev server
    },
    volumes=[
        # Source code with hot reload
        VolumeMount(source=".", target="/app"),
        # Persist node_modules
        VolumeMount(
            source="react-node-modules",
            target="/app/node_modules",
            type="named"
        ),
        # npm cache
        VolumeMount(
            source="npm-cache",
            target="/root/.npm",
            type="named"
        )
    ],
    environment={
        "NODE_ENV": "development",
        "CHOKIDAR_USEPOLLING": "true",  # For file watching in Docker
        "REACT_APP_API_URL": "http://localhost:5000"
    }
)
```

**Workflow:**
```bash
# Start environment
dev-env up react-app.py

# Initial setup
dev-env exec react-app npm install

# Start development server
dev-env exec react-app npm start

# Or SSH in for interactive development
dev-env ssh react-app
npm run test -- --watch
```

### Express.js API

```python
# express-api.py
from dev_env.config import Environment, GitConfig, VolumeMount

environment = Environment(
    name="express-api",
    base_image="node:20",
    git=GitConfig(
        url="git@github.com:company/express-api.git"
    ),
    ports={
        22: {"HostPort": 2224},
        5000: {"HostPort": 5000},
        9229: {"HostPort": 9229}  # Node debugger
    },
    volumes=[
        VolumeMount(source="./src", target="/app/src"),
        VolumeMount(source="./package.json", target="/app/package.json"),
        VolumeMount(
            source="express-node-modules",
            target="/app/node_modules",
            type="named"
        )
    ],
    environment={
        "NODE_ENV": "development",
        "PORT": "5000",
        "DATABASE_URL": "mongodb://localhost:27017/myapp"
    },
    command=["npm", "run", "dev"]  # Assumes nodemon setup
)
```

## Full-Stack Applications

### MERN Stack (MongoDB, Express, React, Node)

```python
# mern-stack.py
from dev_env.config import Environment, GitConfig, VolumeMount, NetworkConfig

# Shared network for all services
app_network = NetworkConfig(name="mern-network")

# MongoDB
mongodb = Environment(
    name="mern-mongodb",
    base_image="mongo:7",
    network=app_network,
    ports={
        27017: {"HostPort": 27017}
    },
    volumes=[
        VolumeMount(
            source="mern-mongo-data",
            target="/data/db",
            type="named"
        )
    ],
    environment={
        "MONGO_INITDB_ROOT_USERNAME": "admin",
        "MONGO_INITDB_ROOT_PASSWORD": "dev-password"
    }
)

# Backend API
backend = Environment(
    name="mern-backend",
    base_image="node:20",
    network=app_network,
    git=GitConfig(
        url="git@github.com:project/mern-backend.git"
    ),
    ports={
        22: {"HostPort": 2225},
        5000: {"HostPort": 5000}
    },
    volumes=[
        VolumeMount(source="./backend", target="/app"),
        VolumeMount(
            source="mern-backend-modules",
            target="/app/node_modules",
            type="named"
        )
    ],
    environment={
        "NODE_ENV": "development",
        "MONGODB_URI": "mongodb://admin:dev-password@mern-mongodb:27017/myapp?authSource=admin",
        "JWT_SECRET": "dev-secret-key"
    }
)

# Frontend React app
frontend = Environment(
    name="mern-frontend",
    base_image="node:20",
    network=app_network,
    git=GitConfig(
        url="git@github.com:project/mern-frontend.git"
    ),
    ports={
        22: {"HostPort": 2226},
        3000: {"HostPort": 3000}
    },
    volumes=[
        VolumeMount(source="./frontend", target="/app"),
        VolumeMount(
            source="mern-frontend-modules",
            target="/app/node_modules",
            type="named"
        )
    ],
    environment={
        "NODE_ENV": "development",
        "REACT_APP_API_URL": "http://localhost:5000"
    }
)

environments = {
    "mongodb": mongodb,
    "backend": backend,
    "frontend": frontend
}
```

**Workflow:**
```bash
# Start all services
dev-env up mern-stack.py  # Starts mongodb
dev-env up mern-stack.py --name mern-backend
dev-env up mern-stack.py --name mern-frontend

# Install dependencies
dev-env exec mern-backend npm install
dev-env exec mern-frontend npm install

# Start services
dev-env exec mern-backend npm run dev
dev-env exec mern-frontend npm start

# Monitor all logs
dev-env logs mern-mongodb -f &
dev-env logs mern-backend -f &
dev-env logs mern-frontend -f &
```

## Database-Backed Applications

### PostgreSQL Development

```python
# postgres-dev.py
from dev_env.config import Environment, VolumeMount

environment = Environment(
    name="postgres-dev",
    base_image="postgres:16-alpine",
    ports={
        5432: {"HostPort": 5432}
    },
    volumes=[
        # Data persistence
        VolumeMount(
            source="postgres-data",
            target="/var/lib/postgresql/data",
            type="named"
        ),
        # Init scripts
        VolumeMount(
            source="./db/init",
            target="/docker-entrypoint-initdb.d",
            mode="ro"
        ),
        # Backup directory
        VolumeMount(
            source="./backups",
            target="/backups"
        )
    ],
    environment={
        "POSTGRES_USER": "devuser",
        "POSTGRES_PASSWORD": "devpass",
        "POSTGRES_DB": "devdb",
        "POSTGRES_HOST_AUTH_METHOD": "trust"  # For development only!
    }
)
```

**Database Management Workflow:**
```bash
# Start database
dev-env up postgres-dev.py

# Connect with psql
dev-env exec postgres-dev psql -U devuser -d devdb

# Import data
dev-env exec postgres-dev psql -U devuser devdb < /backups/dump.sql

# Create backup
dev-env exec postgres-dev pg_dump -U devuser devdb > backup.sql

# Run migrations (from app environment)
dev-env exec myapp alembic upgrade head
```

### Redis + Application

```python
# redis-app.py
from dev_env.config import Environment, NetworkConfig, VolumeMount

app_network = NetworkConfig(name="cache-network")

# Redis cache
redis = Environment(
    name="redis-cache",
    base_image="redis:7-alpine",
    network=app_network,
    ports={
        6379: {"HostPort": 6379}
    },
    volumes=[
        VolumeMount(
            source="redis-data",
            target="/data",
            type="named"
        )
    ],
    command=["redis-server", "--appendonly", "yes"]
)

# Application using Redis
app = Environment(
    name="cached-app",
    base_image="python:3.13",
    network=app_network,
    git=GitConfig(
        url="git@github.com:project/cached-app.git"
    ),
    ports={
        22: {"HostPort": 2227},
        8000: {"HostPort": 8000}
    },
    environment={
        "REDIS_URL": "redis://redis-cache:6379/0"
    }
)

environments = {"redis": redis, "app": app}
```

## CI/CD Integration

### GitHub Actions Integration

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dev-env
        run: |
          pip install -e .
      
      - name: Run tests in environment
        run: |
          dev-env up test-env.py
          dev-env exec test-app pytest --cov
          dev-env down test-app --volumes
```

### Local CI Testing

```python
# ci-test.py
from dev_env.config import Environment, VolumeMount

environment = Environment(
    name="ci-test",
    base_image="python:3.13",
    volumes=[
        # Mount source code
        VolumeMount(source=".", target="/app"),
        # Separate cache for CI
        VolumeMount(
            source="ci-pip-cache",
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

**Local CI Workflow:**
```bash
#!/bin/bash
# run-ci.sh

set -e

echo "Starting CI environment..."
dev-env up ci-test.py

echo "Installing dependencies..."
dev-env exec ci-test pip install -r requirements.txt
dev-env exec ci-test pip install -r requirements-dev.txt

echo "Running linters..."
dev-env exec ci-test black --check .
dev-env exec ci-test flake8
dev-env exec ci-test mypy .

echo "Running tests..."
dev-env exec ci-test pytest --cov=src --cov-report=html

echo "Cleaning up..."
dev-env down ci-test

echo "CI passed! ✅"
```

## Team Collaboration

### Shared Development Server

```python
# team-dev.py
from dev_env.config import Environment, GitConfig, VolumeMount

def create_team_env(developer_name: str, port_offset: int):
    """Create consistent environment for team member"""
    return Environment(
        name=f"app-{developer_name}",
        base_image="company/dev-image:latest",
        git=GitConfig(
            url="git@github.com:company/main-app.git",
            branch=f"feature/{developer_name}"
        ),
        ports={
            22: {"HostPort": 2222 + port_offset},
            8000: {"HostPort": 8000 + port_offset}
        },
        volumes=[
            # Shared team configuration
            VolumeMount(
                source="/shared/team-config",
                target="/app/config",
                mode="ro"
            ),
            # Personal workspace
            VolumeMount(
                source=f"workspace-{developer_name}",
                target="/app",
                type="named"
            )
        ],
        environment={
            "DEVELOPER": developer_name,
            "ENV_TYPE": "development"
        }
    )

# Create environments for team
environments = {
    "alice": create_team_env("alice", 0),
    "bob": create_team_env("bob", 10),
    "charlie": create_team_env("charlie", 20)
}
```

## Best Practices

### 1. Configuration Management

- Keep environment configs in version control
- Use templates for similar projects
- Separate configs for different stages (dev, test, prod)

### 2. Volume Strategy

- **Named volumes** for data that should persist (databases, caches)
- **Bind mounts** for code that needs live editing
- **Read-only mounts** for sensitive configs

### 3. Security Practices

- Never hardcode secrets in configs
- Use read-only mounts for credentials
- Run containers as non-root users
- Limit network exposure to localhost

### 4. Performance Optimization

```python
# Optimized configuration
environment = Environment(
    name="fast-app",
    base_image="python:3.13-slim",  # Use slim images
    volumes=[
        # Cache everything possible
        VolumeMount(
            source="pip-cache",
            target="/root/.cache/pip",
            type="named"
        ),
        VolumeMount(
            source="build-cache",
            target="/app/.build",
            type="named"
        )
    ],
    # Limit resources to prevent system slowdown
    memory="2g",
    cpus=2.0
)
```

### 5. Development vs Production Parity

```python
# dev.py - Development config
dev_env = Environment(
    name="myapp-dev",
    base_image="myapp:dev",
    environment={
        "DEBUG": "true",
        "LOG_LEVEL": "debug"
    }
)

# staging.py - Staging config
staging_env = Environment(
    name="myapp-staging",
    base_image="myapp:latest",  # Same as production
    environment={
        "DEBUG": "false",
        "LOG_LEVEL": "info"
    },
    # Production-like constraints
    memory="512m",
    cpus=1.0
)
```

For more configuration options, see the [Configuration Guide](configuration.md). For troubleshooting common issues, see the [Troubleshooting Guide](troubleshooting.md).