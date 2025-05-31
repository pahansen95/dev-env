# State Management Design

This document details the SQLite-based state persistence system that tracks development environments across sessions.

## Design Requirements

The state management system must:

1. **Persist Environment Metadata**: Track containers across Docker restarts
2. **Handle Concurrent Access**: Multiple CLI invocations
3. **Maintain Consistency**: Atomic updates and rollback
4. **Support Evolution**: Schema migrations for updates
5. **Enable Cleanup**: Detect and remove orphaned state

## Architecture Overview

### State Manager Components

```
StateManager
     │
     ├── Database Layer (SQLite)
     │   ├── Schema Definition
     │   ├── Connection Management
     │   └── Transaction Control
     │
     ├── Environment Operations
     │   ├── Save Environment
     │   ├── Load Environment
     │   ├── List Environments
     │   └── Remove Environment
     │
     ├── Data Validation
     │   ├── JSON Serialization
     │   ├── Type Checking
     │   └── Constraint Validation
     │
     └── Maintenance
         ├── Schema Migration
         ├── Orphan Detection
         └── State Cleanup
```

## Database Schema

### Current Schema (v1)

```sql
-- Main environments table
CREATE TABLE environments (
    name TEXT PRIMARY KEY,           -- Unique environment name
    container_id TEXT NOT NULL,      -- Docker container ID
    container_name TEXT NOT NULL,    -- Docker container name
    config TEXT NOT NULL,            -- JSON configuration
    volumes TEXT,                    -- JSON array of volume names
    network TEXT,                    -- Network name (nullable)
    created_at TEXT NOT NULL,        -- ISO timestamp
    updated_at TEXT NOT NULL         -- ISO timestamp
);

-- Metadata table for schema version, etc.
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,            -- Metadata key
    value TEXT NOT NULL              -- Metadata value
);

-- Indexes for performance
CREATE INDEX idx_container_id ON environments(container_id);
CREATE INDEX idx_created_at ON environments(created_at);
```

### Design Rationale

**Why SQLite?**
- Zero external dependencies (included in Python)
- ACID compliance for data integrity
- Single file storage
- Excellent performance for our use case
- Built-in transaction support

**Schema Decisions:**
- **Primary Key**: Environment name for easy lookup
- **JSON Storage**: Flexibility for complex configuration
- **Timestamps**: ISO format for cross-platform compatibility
- **Nullable Network**: Not all environments use custom networks

## Implementation Details

### Connection Management

```python
@contextlib.contextmanager
def _get_conn(self):
    """Get database connection with automatic commit/rollback"""
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Key Features:**
- Context manager for automatic cleanup
- Row factory for dict-like access
- Automatic commit on success
- Automatic rollback on error

### State Storage

```python
def save_environment(self, name: str, state: dict[str, Any]) -> None:
    """Save environment state"""
    now = datetime.utcnow().isoformat()
    
    with self._get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO environments
            (name, container_id, container_name, config, volumes, network, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?,
                COALESCE((SELECT created_at FROM environments WHERE name = ?), ?),
                ?)
        """, (
            name,
            state["container_id"],
            state["container_name"],
            json.dumps(state.get("config", {})),
            json.dumps(state.get("volumes", [])),
            state.get("network"),
            name,  # For the COALESCE subquery
            now,   # For new records
            now,   # updated_at
        ))
```

**Design Choices:**
- `INSERT OR REPLACE` for idempotent updates
- `COALESCE` preserves original creation time
- JSON serialization for complex data
- Atomic operation (single SQL statement)

### State Retrieval

```python
def get_environment(self, name: str) -> dict[str, Any] | None:
    """Get environment state by name"""
    with self._get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM environments WHERE name = ?",
            (name,)
        ).fetchone()
        
        if not row:
            return None
        
        return {
            "name": row["name"],
            "container_id": row["container_id"],
            "container_name": row["container_name"],
            "config": json.loads(row["config"]),
            "volumes": json.loads(row["volumes"] or "[]"),
            "network": row["network"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
```

**JSON Handling:**
- Deserialize on read
- Handle null values gracefully
- Type-safe dictionary return

## Transaction Management

### Atomic Operations

All state changes are atomic:

```python
def update_environment_volumes(self, name: str, volumes: list[str]) -> None:
    """Update just the volumes for an environment"""
    with self._get_conn() as conn:
        # Single transaction for consistency
        conn.execute("BEGIN")
        try:
            # Verify environment exists
            exists = conn.execute(
                "SELECT 1 FROM environments WHERE name = ?",
                (name,)
            ).fetchone()
            
            if not exists:
                raise EnvironmentNotFoundError(name)
            
            # Update volumes
            conn.execute(
                "UPDATE environments SET volumes = ?, updated_at = ? WHERE name = ?",
                (json.dumps(volumes), datetime.utcnow().isoformat(), name)
            )
            
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
```

### Concurrent Access

SQLite handles concurrent access with:

```python
# Set reasonable timeout for lock acquisition
conn = sqlite3.connect(self.db_path, timeout=10.0)

# Enable Write-Ahead Logging for better concurrency
conn.execute("PRAGMA journal_mode=WAL")

# Ensure data integrity
conn.execute("PRAGMA synchronous=NORMAL")
```

## Schema Evolution

### Migration System

```python
def _init_db(self):
    """Initialize database schema with migrations"""
    with self._get_conn() as conn:
        # Create initial schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS environments (...)
        """)
        
        # Get current version
        version = self._get_schema_version(conn)
        
        # Apply migrations
        if version < 2:
            self._migrate_v1_to_v2(conn)
        if version < 3:
            self._migrate_v2_to_v3(conn)
        
        # Update version
        self._set_schema_version(conn, CURRENT_SCHEMA_VERSION)

def _migrate_v1_to_v2(self, conn):
    """Add network column (example migration)"""
    try:
        conn.execute("ALTER TABLE environments ADD COLUMN network TEXT")
    except sqlite3.OperationalError:
        # Column already exists
        pass
```

### Migration Strategy

1. **Non-Breaking Changes**: Add columns with defaults
2. **Data Transformation**: Migrate in transaction
3. **Backwards Compatibility**: Support reading old data
4. **Version Tracking**: Store schema version in metadata

## Data Integrity

### Constraints

```sql
-- Enforce data integrity at database level
CREATE TABLE environments (
    name TEXT PRIMARY KEY,
    container_id TEXT NOT NULL CHECK(length(container_id) = 64),
    container_name TEXT NOT NULL CHECK(container_name != ''),
    config TEXT NOT NULL CHECK(json_valid(config)),
    volumes TEXT CHECK(volumes IS NULL OR json_valid(volumes)),
    network TEXT,
    created_at TEXT NOT NULL CHECK(datetime(created_at) IS NOT NULL),
    updated_at TEXT NOT NULL CHECK(datetime(updated_at) IS NOT NULL),
    CHECK(datetime(updated_at) >= datetime(created_at))
);
```

### Validation

```python
def validate_state(self, state: dict[str, Any]) -> None:
    """Validate state before storage"""
    # Required fields
    required = ["container_id", "container_name", "config"]
    for field in required:
        if field not in state:
            raise ValueError(f"Missing required field: {field}")
    
    # Container ID format (64 hex chars)
    if not re.match(r"^[a-f0-9]{64}$", state["container_id"]):
        raise ValueError("Invalid container ID format")
    
    # Config must be dict
    if not isinstance(state.get("config"), dict):
        raise ValueError("Config must be a dictionary")
    
    # Volumes must be list
    if "volumes" in state and not isinstance(state["volumes"], list):
        raise ValueError("Volumes must be a list")
```

## Orphan Detection

### Finding Orphaned State

```python
def find_orphaned_environments(self) -> list[str]:
    """Find environments with non-existent containers"""
    docker = DockerClient()
    orphaned = []
    
    with self._get_conn() as conn:
        environments = conn.execute(
            "SELECT name, container_id FROM environments"
        ).fetchall()
        
        for env in environments:
            try:
                # Check if container exists
                docker.inspect_container(env["container_id"])
            except ContainerNotFoundError:
                orphaned.append(env["name"])
    
    return orphaned
```

### Cleanup Strategy

```python
def cleanup_orphaned_state(self, dry_run: bool = True) -> int:
    """Remove state for non-existent containers"""
    orphaned = self.find_orphaned_environments()
    
    if dry_run:
        print(f"Would remove {len(orphaned)} orphaned environments:")
        for name in orphaned:
            print(f"  - {name}")
        return len(orphaned)
    
    removed = 0
    with self._get_conn() as conn:
        for name in orphaned:
            conn.execute(
                "DELETE FROM environments WHERE name = ?",
                (name,)
            )
            removed += 1
    
    return removed
```

## Performance Optimization

### Query Optimization

```python
# Efficient listing with container status
def list_environments_with_status(self) -> list[dict]:
    """List all environments with current container status"""
    docker = DockerClient()
    
    with self._get_conn() as conn:
        # Fetch all environments in one query
        environments = conn.execute("""
            SELECT name, container_id, created_at, updated_at
            FROM environments
            ORDER BY updated_at DESC
        """).fetchall()
        
        # Batch container status checks
        container_ids = [env["container_id"] for env in environments]
        statuses = docker.batch_inspect_containers(container_ids)
        
        # Combine results
        results = []
        for env in environments:
            status = statuses.get(env["container_id"], {"State": {"Status": "missing"}})
            results.append({
                "name": env["name"],
                "container_id": env["container_id"],
                "status": status["State"]["Status"],
                "created_at": env["created_at"],
                "updated_at": env["updated_at"]
            })
        
        return results
```

### Indexing Strategy

```sql
-- Indexes for common queries
CREATE INDEX idx_container_id ON environments(container_id);     -- Container lookups
CREATE INDEX idx_created_at ON environments(created_at);         -- Time-based queries
CREATE INDEX idx_updated_at ON environments(updated_at);         -- Recent activity

-- Composite index for status queries
CREATE INDEX idx_name_container ON environments(name, container_id);
```

## Error Handling

### Common Error Scenarios

```python
class StateError(DevEnvError):
    """Base class for state management errors"""
    pass

class DatabaseError(StateError):
    """Database operation failed"""
    pass

class EnvironmentNotFoundError(StateError):
    """Environment not found in state"""
    def __init__(self, name: str):
        super().__init__(f"Environment '{name}' not found")
        self.name = name

class StateCorruptionError(StateError):
    """State database is corrupted"""
    pass
```

### Recovery Procedures

```python
def repair_database(self) -> None:
    """Attempt to repair corrupted database"""
    try:
        with self._get_conn() as conn:
            # Check integrity
            result = conn.execute("PRAGMA integrity_check").fetchone()
            if result[0] != "ok":
                raise StateCorruptionError("Database integrity check failed")
            
            # Vacuum to reclaim space
            conn.execute("VACUUM")
            
            # Reindex
            conn.execute("REINDEX")
            
    except sqlite3.DatabaseError as e:
        # Backup corrupted database
        backup_path = self.db_path.with_suffix(".corrupted")
        shutil.copy(self.db_path, backup_path)
        
        # Recreate database
        self.db_path.unlink()
        self._init_db()
        
        raise StateCorruptionError(
            f"Database was corrupted and has been reset. "
            f"Old database backed up to {backup_path}"
        )
```

## Testing Strategies

### Unit Tests

```python
def test_state_persistence():
    """Test basic state save/load cycle"""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_mgr = StateManager(Path(tmpdir))
        
        # Save state
        state = {
            "container_id": "a" * 64,
            "container_name": "test-container",
            "config": {"image": "python:3.13"},
            "volumes": ["test-volume"],
            "network": "test-network"
        }
        state_mgr.save_environment("test-env", state)
        
        # Load state
        loaded = state_mgr.get_environment("test-env")
        assert loaded["container_id"] == state["container_id"]
        assert loaded["config"] == state["config"]
        assert loaded["volumes"] == state["volumes"]
```

### Integration Tests

```python
def test_concurrent_access():
    """Test concurrent state updates"""
    import threading
    
    state_mgr = StateManager(test_db_path)
    errors = []
    
    def update_environment(name, count):
        try:
            for i in range(count):
                state_mgr.save_environment(name, {
                    "container_id": "b" * 64,
                    "container_name": f"container-{i}",
                    "config": {"iteration": i}
                })
        except Exception as e:
            errors.append(e)
    
    # Run concurrent updates
    threads = []
    for i in range(5):
        t = threading.Thread(
            target=update_environment,
            args=(f"env-{i}", 100)
        )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    assert len(errors) == 0
```

## Future Enhancements

### Potential Improvements

1. **Event Log**: Track all state changes with timestamps
2. **Soft Deletes**: Mark as deleted instead of removing
3. **State Snapshots**: Periodic backups of state
4. **Metrics Collection**: Track environment usage patterns
5. **Encryption**: Encrypt sensitive configuration data

### Schema V2 Proposal

```sql
-- Enhanced schema with history
CREATE TABLE environment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_name TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- created, updated, started, stopped, deleted
    event_data TEXT,           -- JSON event details
    timestamp TEXT NOT NULL,
    FOREIGN KEY (environment_name) REFERENCES environments(name)
);

-- Usage metrics
CREATE TABLE environment_metrics (
    environment_name TEXT NOT NULL,
    metric_date DATE NOT NULL,
    total_runtime_seconds INTEGER DEFAULT 0,
    start_count INTEGER DEFAULT 0,
    exec_count INTEGER DEFAULT 0,
    PRIMARY KEY (environment_name, metric_date),
    FOREIGN KEY (environment_name) REFERENCES environments(name)
);
```

## Conclusion

The SQLite-based state management system provides a robust, zero-dependency solution for tracking development environments. By leveraging SQLite's ACID properties and transaction support, the system ensures data integrity while maintaining simplicity and performance.

The design balances functionality with maintainability, providing essential features like orphan detection and schema migration while avoiding unnecessary complexity.

For related architectural components, see:
- [Architecture Overview](overview.md)
- [Docker Client](docker-client.md)
- [Container Lifecycle](container-lifecycle.md)