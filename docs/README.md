# Dev-Env Documentation

Welcome to the dev-env documentation! Dev-env provides rapidly deployable, isolated development environments using Docker containers with zero external dependencies.

## 🚀 Quick Start

New to dev-env? Start here:

- **[Getting Started Guide](user/getting-started.md)** - Get up and running in 5 minutes
- **[Installation](user/getting-started.md#installation-30-seconds)** - Install dev-env
- **[Your First Environment](user/getting-started.md#your-first-environment-2-minutes)** - Create your first development environment

## 📚 Documentation Structure

### For Users

Learn how to use dev-env for your development workflow:

#### Essentials
- **[Getting Started](user/getting-started.md)** - 5-minute bootstrap guide
- **[Configuration Guide](user/configuration.md)** - Complete environment configuration reference
- **[Command Reference](user/commands.md)** - All CLI commands with examples

#### Advanced Usage
- **[Development Workflows](user/workflows.md)** - Language-specific patterns and best practices
- **[Troubleshooting](user/troubleshooting.md)** - Solutions to common problems

### For Developers

Integrate and extend dev-env:

#### Integration
- **[Integration Guide](developer/integration.md)** - CI/CD, IDE, and project integration
- **[API Reference](developer/api-reference.md)** - Complete module documentation

#### Extension
- **[Extension Patterns](developer/extending.md)** - Custom images, templates, and hooks
- **[Security Model](developer/security-model.md)** - Security implementation and compliance

### Architecture & Design

Understanding dev-env internals:

- **[Design Document](design.md)** - System architecture and design decisions
- **[Architecture Overview](architecture/overview.md)** *(coming soon)* - Component interaction
- **[Docker Client](architecture/docker-client.md)** *(coming soon)* - Zero-dependency implementation
- **[State Management](architecture/state-management.md)** *(coming soon)* - SQLite persistence
- **[Container Lifecycle](architecture/container-lifecycle.md)** *(coming soon)* - Initialization pipeline

## 🎯 Common Use Cases

### By Language

#### Python Development
- [Basic Python Project](user/workflows.md#basic-python-project)
- [Django Web Application](user/workflows.md#django-web-application)
- [FastAPI Microservice](user/workflows.md#fastapi-microservice)

#### Node.js Development
- [React Application](user/workflows.md#react-application)
- [Express.js API](user/workflows.md#expressjs-api)

#### Full-Stack Development
- [MERN Stack](user/workflows.md#mern-stack-mongodb-express-react-node)
- [PostgreSQL Applications](user/workflows.md#postgresql-development)

### By Task

#### Environment Management
- [Create Environment](user/commands.md#up---create-and-start-environment)
- [List Environments](user/commands.md#list---list-environments)
- [Stop Environment](user/commands.md#down---stop-and-remove-environment)

#### Development Tasks
- [Execute Commands](user/commands.md#exec---execute-command)
- [SSH Access](user/commands.md#ssh---ssh-access)
- [View Logs](user/commands.md#logs---view-logs)

#### Configuration
- [Port Mapping](user/configuration.md#port-configuration)
- [Volume Mounts](user/configuration.md#volume-management)
- [Environment Variables](user/configuration.md#environment-variables)

## 🔧 Configuration Examples

### Minimal Configuration
```python
from dev_env.config import Environment

environment = Environment(
    name="myproject",
    base_image="python:3.13"
)
```

### Web Application
```python
from dev_env.config import Environment, GitConfig

environment = Environment(
    name="webapp",
    base_image="python:3.13",
    git=GitConfig(url="https://github.com/user/webapp.git"),
    ports={
        8000: {"HostPort": 8000}
    }
)
```

### Full Stack with Database
```python
from dev_env.config import Environment, NetworkConfig

network = NetworkConfig(name="app-network")

db = Environment(
    name="database",
    base_image="postgres:16",
    network=network,
    environment={
        "POSTGRES_DB": "myapp",
        "POSTGRES_USER": "user",
        "POSTGRES_PASSWORD": "pass"
    }
)

app = Environment(
    name="webapp",
    base_image="python:3.13",
    network=network,
    environment={
        "DATABASE_URL": "postgresql://user:pass@database:5432/myapp"
    }
)
```

## 🛡️ Security Features

Dev-env implements secure-by-default practices:

- **Non-root execution** - Containers run as unprivileged users
- **Network isolation** - Isolated Docker networks by default
- **Port restrictions** - Localhost-only port binding
- **SSH security** - Key-based authentication only
- **Volume protection** - System directories protected from mounting

Learn more in the [Security Model](developer/security-model.md).

## 🤝 Contributing

Want to contribute to dev-env?

- **[Contributing Guide](contributing.md)** *(coming soon)* - Development setup and guidelines
- **[Issue Tracker](https://github.com/yourusername/dev-env/issues)** - Report bugs or request features
- **[Discussions](https://github.com/yourusername/dev-env/discussions)** - Ask questions and share ideas

## 📖 Additional Resources

### Guides by Experience Level

#### Beginners
1. [Getting Started](user/getting-started.md)
2. [Basic Commands](user/commands.md#core-commands)
3. [Simple Python Workflow](user/workflows.md#basic-python-project)

#### Intermediate
1. [Configuration Guide](user/configuration.md)
2. [Development Workflows](user/workflows.md)
3. [Troubleshooting](user/troubleshooting.md)

#### Advanced
1. [Extension Patterns](developer/extending.md)
2. [API Reference](developer/api-reference.md)
3. [Security Model](developer/security-model.md)

### Migration Guides

- [From Docker Compose](user/workflows.md#converting-from-docker-compose)
- [From Vagrant](user/getting-started.md#from-vagrant)

### FAQ

**Q: What are the requirements?**
A: Python 3.13+ and Docker. That's it!

**Q: How is this different from Docker Compose?**
A: Dev-env focuses on development environments with built-in SSH, git integration, and Python-based configuration.

**Q: Can I use custom Docker images?**
A: Yes! See [Custom Base Images](developer/extending.md#custom-base-images).

**Q: Is it production-ready?**
A: Dev-env is designed for development environments. For production, use proper orchestration tools.

## 🔍 Search Documentation

Looking for something specific?

- Use your browser's search (Ctrl/Cmd + F) on this page
- Check the table of contents in each guide
- Browse by category above

## 📝 Documentation Status

| Section | Status | Description |
|---------|--------|-------------|
| User Guides | ✅ Complete | All user documentation is available |
| Developer Guides | ✅ Complete | Integration and extension documentation |
| Architecture | 🚧 In Progress | Internal design documentation |
| Contributing | 📋 Planned | Contribution guidelines |

---

**Need help?** Start with the [Getting Started Guide](user/getting-started.md) or check the [Troubleshooting Guide](user/troubleshooting.md) for common issues.