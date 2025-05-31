# The SSH Developer's Guide

A comprehensive guide for developers who integrate and work with SSH, covering modern security practices, implementation patterns, and operational strategies.

## Table of Contents

**Part 1: SSH Fundamentals**
- [What SSH Provides](#what-ssh-provides)
- [The Three-Layer Architecture](#the-three-layer-architecture)
- [How SSH Connections Work](#how-ssh-connections-work)

**Part 2: Authentication and Security**
- [Modern Algorithm Selection](#modern-algorithm-selection)
- [Authentication Methods](#authentication-methods)
- [Host Verification and Trust](#host-verification-and-trust)
- [Security Requirements](#security-requirements)

**Part 3: Working with SSH**
- [Client Implementation](#client-implementation)
- [Server Implementation](#server-implementation)
- [Channel Management](#channel-management)
- [Configuration Patterns](#configuration-patterns)

**Part 4: Advanced Implementation**
- [Binary Protocol Details](#binary-protocol-details)
- [Performance Optimization](#performance-optimization)
- [Extension Negotiation](#extension-negotiation)
- [Certificate Authentication](#certificate-authentication)

**Part 5: Operations and Migration**
- [Deployment Strategies](#deployment-strategies)
- [Legacy System Migration](#legacy-system-migration)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
- [Future-Proofing](#future-proofing)

**[Technical Reference Index](#technical-reference-index)**

---

# Part 1: SSH Fundamentals

## What SSH Provides

SSH (Secure Shell) enables secure communication over insecure networks through cryptographic protection. For developers, SSH provides three essential capabilities:

**Secure Remote Access**
SSH replaces insecure protocols like telnet and rlogin with encrypted communication channels. Every byte transmitted is protected against eavesdropping and tampering.

**Authenticated Communication**
Both server and client identities are cryptographically verified. This mutual authentication prevents man-in-the-middle attacks and ensures you're connecting to the intended system.

**Multiplexed Channels**
A single SSH connection supports multiple independent data streams. You can run commands, transfer files, and forward ports simultaneously over one encrypted tunnel.

## The Three-Layer Architecture

SSH implements a clean separation of concerns through three protocol layers:

### Transport Layer Protocol (RFC 4253)

The transport layer establishes the secure foundation:

```
Responsibilities:
- Initial connection and version negotiation
- Key exchange and server authentication  
- Encryption and integrity protection
- Packet-level communication
```

This layer creates an encrypted tunnel but knows nothing about users or services. It's purely focused on secure communication between two endpoints.

### User Authentication Protocol (RFC 4252)

The authentication layer verifies user identity:

```
Responsibilities:
- User credential verification
- Multiple authentication method support
- Session binding to prevent replay attacks
- Authentication method negotiation
```

This layer is server-driven - the server tells the client which authentication methods are acceptable and in what order they should be tried.

### Connection Protocol (RFC 4254)

The connection layer provides services:

```
Responsibilities:
- Channel multiplexing
- Interactive shell sessions
- Command execution
- Port forwarding
- Subsystem invocation (like SFTP)
```

Each layer depends on the security guarantees of the layer below it, creating a robust security architecture.

## How SSH Connections Work

Understanding the SSH connection flow helps developers debug issues and implement SSH correctly.

### Protocol Flow

```
Client                                    Server
------                                    ------
TCP Connect (port 22) ─────────────────────────►
                                          
Protocol Version Exchange:
"SSH-2.0-ClientSoftware_1.0" ─────────────────►
                            ◄───────────────── "SSH-2.0-ServerSoftware_2.0"

Key Exchange Initialization:
KEXINIT (supported algorithms) ───────────────►
                              ◄─────────────── KEXINIT (supported algorithms)

[Algorithm negotiation happens here]

Diffie-Hellman Key Exchange:
DH_INIT ──────────────────────────────────────►
        ◄──────────────────────────────────── DH_REPLY + Host Key + Signature

NEW_KEYS ─────────────────────────────────────►
         ◄───────────────────────────────────── NEW_KEYS

[Encryption begins]

Service Request:
SERVICE_REQUEST ("ssh-userauth") ─────────────►
                                ◄───────────── SERVICE_ACCEPT

Authentication:
USERAUTH_REQUEST ─────────────────────────────►
                 ◄───────────────────────────── USERAUTH_SUCCESS/FAILURE

Channel Operations:
CHANNEL_OPEN ─────────────────────────────────►
             ◄───────────────────────────────── CHANNEL_OPEN_CONFIRMATION

CHANNEL_DATA ◄────────────────────────────────►
```

### Key Points for Developers

**Version String Requirements**
- Must start with "SSH-2.0-"
- No spaces in software version
- Total line ≤ 255 characters
- Terminated with CR LF

**Algorithm Negotiation**
- First matching algorithm from client and server lists is used
- Order matters - list preferred algorithms first
- Different algorithms can be used in each direction

**Encryption Timing**
- Everything before NEW_KEYS is plaintext
- NEW_KEYS message itself is not encrypted
- All subsequent packets are encrypted

---

# Part 2: Authentication and Security

## Modern Algorithm Selection

Choosing the right algorithms is critical for SSH security. The landscape has shifted significantly, with many traditional algorithms now deprecated.

### Current Security Requirements (2024)

**Minimum Security Strength: 112 bits**

This translates to specific requirements:
- RSA keys: 2048-bit minimum, 3072-bit recommended
- Diffie-Hellman: Group14 (2048-bit) minimum
- Elliptic Curves: P-256 minimum
- Symmetric Ciphers: AES-128 minimum
- Hash Functions: SHA-256 minimum

### Algorithm Hierarchy

**Public Key Algorithms** (Strongest First)
```
ssh-ed25519           - Best: Fast, secure, small keys (32 bytes)
ssh-ed448             - Higher security margin (57 bytes)
ecdsa-sha2-nistp256   - Good but complex implementation
ecdsa-sha2-nistp384   - Higher security NIST curve
ecdsa-sha2-nistp521   - Highest security NIST curve
rsa-sha2-512          - RSA with SHA-512 signatures
rsa-sha2-256          - RSA with SHA-256 signatures
ssh-rsa               - DEPRECATED: Uses SHA-1
ssh-dss               - REMOVED: Multiple weaknesses
```

**Key Exchange Methods**
```
mlkem768x25519-sha256        - Post-quantum resistant
curve25519-sha256            - Best current: Fast and secure
curve448-sha512              - Higher security margin
diffie-hellman-group16-sha512 - Traditional DH, 4096-bit
diffie-hellman-group14-sha256 - Minimum acceptable DH
diffie-hellman-group14-sha1   - DEPRECATED: SHA-1
diffie-hellman-group1-sha1    - DEPRECATED: 1024-bit
```

### The RSA Signature Algorithm Distinction

A critical point of confusion for many developers:

```python
# The public key format is always "ssh-rsa"
public_key_algorithm = "ssh-rsa"

# But signatures can use different hash functions
signature_algorithms = [
    "rsa-sha2-512",  # Uses SHA-512
    "rsa-sha2-256",  # Uses SHA-256  
    "ssh-rsa"        # Uses SHA-1 (deprecated)
]
```

This means:
- All RSA public keys have algorithm name "ssh-rsa"
- During authentication, you specify which signature algorithm to use
- The same RSA key can produce different signature types

### Performance Characteristics

Algorithm performance varies dramatically:

```
Algorithm         Sign Time    Verify Time    Key Size
------------------------------------------------------
Ed25519          1.0x         1.0x           32 bytes
ECDSA-P256       3.0x         6.0x           64 bytes
RSA-2048         20x          0.3x           256 bytes
RSA-4096         100x         0.5x           512 bytes
```

For high-frequency operations (like CI/CD systems), Ed25519's performance advantage is significant.

## Authentication Methods

SSH authentication is fundamentally server-driven. The server controls which methods are acceptable and in what order.

### Authentication Flow

```python
# Server evaluates each authentication attempt
def process_auth_request(username, service, method, data):
    if method == "none":
        # Check if user requires authentication
        if requires_auth(username):
            return FAILURE, ["publickey", "password", "keyboard-interactive"]
        else:
            return SUCCESS
    
    elif method == "publickey":
        # Note: algorithm in request may differ from key type
        key_algo = data.algorithm  # e.g., "rsa-sha2-256"
        public_key = data.key      # Has type "ssh-rsa" for RSA
        
        if not is_authorized(username, public_key):
            return FAILURE, available_methods
            
        if data.signature:
            # Verify signature uses claimed algorithm
            if verify_signature(data.signature, key_algo):
                return SUCCESS
        else:
            # Client is querying if key is acceptable
            return FAILURE, available_methods
    
    elif method == "password":
        if verify_password(username, data.password):
            if requires_2fa(username):
                # Partial success - need additional auth
                return PARTIAL_SUCCESS, ["keyboard-interactive"]
            else:
                return SUCCESS
```

### Public Key Authentication Details

Modern public key authentication must handle multiple signature algorithms:

```python
def verify_public_key_signature(request):
    # Extract components
    session_id = get_session_id()
    username = request.username
    service = request.service
    key_algorithm = request.algorithm
    public_key = request.public_key
    signature = request.signature
    
    # Reconstruct signed data
    signed_data = encode(
        session_id,
        SSH_MSG_USERAUTH_REQUEST,
        username,
        service,
        "publickey",
        True,
        key_algorithm,  # Algorithm used for signature
        public_key      # Still has "ssh-rsa" type for RSA
    )
    
    # Verify signature matches claimed algorithm
    return verify_signature(
        signature,
        signed_data,
        public_key,
        key_algorithm  # Must match algorithm in signature blob
    )
```

### Multi-Factor Authentication

SSH supports requiring multiple authentication methods:

```bash
# Server configuration
AuthenticationMethods publickey,keyboard-interactive
```

This requires both public key AND another factor, implementing true MFA at the protocol level.

## Host Verification and Trust

SSH provides three models for verifying server identity, each with different security trade-offs.

### Trust On First Use (TOFU)

The most common deployment model:

```python
def verify_host_tofu(hostname, host_key):
    known_hosts = load_known_hosts()
    
    if hostname not in known_hosts:
        # First connection - trust and store
        fingerprint = compute_fingerprint(host_key)
        print(f"The authenticity of host '{hostname}' can't be established.")
        print(f"ED25519 key fingerprint is {fingerprint}.")
        
        if prompt_user("Are you sure you want to continue connecting?"):
            save_known_host(hostname, host_key)
            return True
        return False
    
    # Verify against stored key
    if known_hosts[hostname] != host_key:
        print("WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!")
        print("IT IS POSSIBLE THAT SOMEONE IS DOING SOMETHING NASTY!")
        return False
    
    return True
```

### DNS SSHFP Records

Leverage DNS(SEC) for host key verification:

```python
def verify_host_dns(hostname, host_key):
    # Query SSHFP records
    sshfp_records = dns_query(hostname, 'SSHFP')
    
    if not sshfp_records:
        return None  # Fall back to other methods
    
    # Check DNSSEC validation
    if not dnssec_valid(sshfp_records):
        print("WARNING: SSHFP records not DNSSEC signed")
        return None
    
    # Compute fingerprint
    fp_sha256 = hashlib.sha256(host_key.blob).digest()
    
    # Check against DNS records
    for record in sshfp_records:
        if (record.algorithm == host_key.algorithm and
            record.fp_type == 2 and  # SHA-256
            record.fingerprint == fp_sha256):
            return True
    
    return False
```

### Certificate-Based Verification

The most secure option for organizations:

```python
def verify_host_certificate(cert, hostname):
    # Load trusted CA keys
    ca_keys = load_trusted_cas()
    
    # Verify certificate signature
    if not any(verify_signature(cert.signature, cert.tbs_cert, ca) 
               for ca in ca_keys):
        return False
    
    # Check validity period
    now = time.time()
    if not (cert.valid_after <= now <= cert.valid_before):
        return False
    
    # Verify hostname in principals
    if hostname not in cert.principals:
        return False
    
    # Check critical options
    if not validate_critical_options(cert.critical_options):
        return False
    
    return True
```

## Security Requirements

SSH enforces several security requirements that developers must understand and implement correctly.

### File Permission Requirements

SSH refuses to use files with incorrect permissions:

```python
# Required permissions
PERMISSIONS = {
    '~/.ssh':              0o700,  # drwx------
    '~/.ssh/id_*':         0o600,  # -rw-------
    '~/.ssh/id_*.pub':     0o644,  # -rw-r--r--
    '~/.ssh/config':       0o600,  # -rw-------
    '~/.ssh/authorized_keys': 0o644, # -rw-r--r--
    '~/.ssh/known_hosts':  0o644,  # -rw-r--r--
    '/etc/ssh/ssh_host_*_key': 0o600,  # -rw-------
}

def check_ssh_permissions(path):
    stat_info = os.stat(path)
    
    # Must be owned by user
    if stat_info.st_uid != os.getuid():
        raise PermissionError(f"{path} must be owned by current user")
    
    # Check permissions
    mode = stat_info.st_mode & 0o777
    expected = PERMISSIONS.get(path)
    
    if mode != expected:
        raise PermissionError(
            f"{path} has permissions {oct(mode)}, "
            f"should be {oct(expected)}"
        )
```

### Rekeying Requirements

Long-lived connections must rekey before cryptographic limits:

```python
class RekeyLimits:
    # Maximum values before rekey required
    MAX_PACKETS = (1 << 31) - 1  # Sequence number limit
    MAX_BYTES = 1 << 30         # 1 GB default
    MAX_TIME = 3600             # 1 hour
    
    def should_rekey(self, stats):
        return (stats.packets >= self.MAX_PACKETS or
                stats.bytes >= self.MAX_BYTES or
                time.time() - stats.last_rekey >= self.MAX_TIME)
```

### Constant-Time Operations

Prevent timing attacks in security-critical operations:

```c
/* Constant-time comparison */
int ct_memcmp(const void *a, const void *b, size_t len) {
    const unsigned char *_a = a, *_b = b;
    unsigned char diff = 0;
    
    for (size_t i = 0; i < len; i++) {
        diff |= _a[i] ^ _b[i];
    }
    
    return diff != 0;
}
```

### Random Number Quality

SSH security depends on cryptographically secure random numbers:

```python
def generate_session_id():
    # Use OS-provided CSPRNG
    return os.urandom(32)  # Never use random.random()!

def add_random_padding(data, block_size):
    # Padding must be random to prevent attacks
    padding_length = block_size - (len(data) % block_size)
    if padding_length < 4:
        padding_length += block_size
    
    return data + os.urandom(padding_length)
```

---

# Part 3: Working with SSH

## Client Implementation

Building an SSH client requires handling connection establishment, algorithm negotiation, and authentication.

### Basic Client Structure

```python
class SSHClient:
    def __init__(self):
        self.transport = None
        self.session_id = None
        self.algorithms = {
            'kex': [
                'curve25519-sha256',
                'curve25519-sha256@libssh.org',
                'diffie-hellman-group16-sha512',
                'diffie-hellman-group14-sha256'
            ],
            'host_key': [
                'ssh-ed25519',
                'rsa-sha2-256',
                'rsa-sha2-512',
                'ecdsa-sha2-nistp256'
            ],
            'cipher': [
                'chacha20-poly1305@openssh.com',
                'aes128-gcm@openssh.com',
                'aes256-gcm@openssh.com'
            ],
            'mac': [
                'hmac-sha2-256-etm@openssh.com',
                'hmac-sha2-512-etm@openssh.com'
            ]
        }
    
    def connect(self, hostname, port=22, username=None):
        # Establish TCP connection
        self.transport = self._create_transport(hostname, port)
        
        # Exchange versions
        self._exchange_versions()
        
        # Key exchange
        self.session_id = self._key_exchange()
        
        # Request authentication service
        self._request_service('ssh-userauth')
        
        # Authenticate user
        if username:
            self._authenticate(username)
    
    def _exchange_versions(self):
        # Send client version
        client_version = "SSH-2.0-MySSHClient_1.0\r\n"
        self.transport.send(client_version.encode())
        
        # Read server version
        server_version = self._read_line()
        if not server_version.startswith("SSH-2.0-"):
            raise ValueError("Incompatible SSH version")
```

### Authentication Implementation

```python
def authenticate_publickey(self, username, private_key):
    # First, check if key is acceptable
    public_key = private_key.public_key()
    
    # Determine signature algorithm
    if isinstance(private_key, Ed25519Key):
        key_algorithm = "ssh-ed25519"
    elif isinstance(private_key, RSAKey):
        # Use best available RSA signature algorithm
        key_algorithm = self._select_rsa_algorithm()
    
    # Query if key is acceptable (no signature)
    self._send_userauth_request(
        username=username,
        service="ssh-connection",
        method="publickey",
        has_signature=False,
        algorithm=key_algorithm,
        blob=public_key.encode()
    )
    
    response = self._read_packet()
    if response.type != SSH_MSG_USERAUTH_PK_OK:
        return False
    
    # Key is acceptable, send with signature
    signature = self._sign_auth_request(private_key, key_algorithm)
    
    self._send_userauth_request(
        username=username,
        service="ssh-connection", 
        method="publickey",
        has_signature=True,
        algorithm=key_algorithm,
        blob=public_key.encode(),
        signature=signature
    )
    
    return self._wait_auth_response()
```

### Channel Management

```python
class Channel:
    def __init__(self, client, channel_type="session"):
        self.client = client
        self.channel_type = channel_type
        self.local_id = client._next_channel_id()
        self.remote_id = None
        self.local_window = 2097152  # 2MB
        self.remote_window = 0
        self.local_max_packet = 32768
        self.remote_max_packet = 0
        self.eof_received = False
        self.eof_sent = False
        
    def open(self):
        self.client._send_channel_open(
            channel_type=self.channel_type,
            channel_id=self.local_id,
            window_size=self.local_window,
            max_packet=self.local_max_packet
        )
        
        response = self.client._wait_channel_response()
        if response.type == SSH_MSG_CHANNEL_OPEN_CONFIRMATION:
            self.remote_id = response.sender_channel
            self.remote_window = response.window_size
            self.remote_max_packet = response.max_packet
            return True
        return False
    
    def send(self, data):
        while data:
            # Respect window size and packet limits
            chunk_size = min(
                len(data),
                self.remote_window,
                self.remote_max_packet
            )
            
            if chunk_size == 0:
                # Wait for window adjustment
                self.client._wait_window_adjust(self)
                continue
            
            self.client._send_channel_data(self.remote_id, data[:chunk_size])
            self.remote_window -= chunk_size
            data = data[chunk_size:]
```

## Server Implementation

SSH servers must handle multiple clients, various authentication methods, and concurrent channels.

### Server Architecture

```python
class SSHServer:
    def __init__(self, host_keys):
        self.host_keys = host_keys  # Dict of algorithm -> key
        self.listen_socket = None
        self.clients = []
        
    def listen(self, address='0.0.0.0', port=22):
        self.listen_socket = socket.socket()
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((address, port))
        self.listen_socket.listen(128)
        
        while True:
            client_socket, client_addr = self.listen_socket.accept()
            client_thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket, client_addr)
            )
            client_thread.start()
    
    def _handle_client(self, socket, address):
        try:
            transport = SSHTransport(socket)
            
            # Version exchange
            transport.send(b"SSH-2.0-MySSHServer_1.0\r\n")
            client_version = transport.read_line()
            
            # Key exchange
            session_id = self._perform_key_exchange(transport)
            
            # Authentication
            authenticated_user = self._handle_authentication(transport, session_id)
            
            if authenticated_user:
                # Handle connection protocol
                self._handle_connection(transport, authenticated_user)
                
        except Exception as e:
            logging.error(f"Client {address} error: {e}")
        finally:
            socket.close()
```

### Host Key Selection

```python
def select_host_key(self, client_algorithms):
    """Select best host key algorithm supported by client"""
    
    # Our preference order (fastest/most secure first)
    preference = [
        'ssh-ed25519',
        'ecdsa-sha2-nistp256', 
        'rsa-sha2-512',
        'rsa-sha2-256',
        'ssh-rsa'  # Only if nothing else available
    ]
    
    # Find first match
    for algo in preference:
        if algo in client_algorithms and algo in self.host_keys:
            return algo, self.host_keys[algo]
    
    # Handle RSA special case
    if 'ssh-rsa' in client_algorithms:
        # Client supports RSA but maybe not SHA-2 variants
        for rsa_variant in ['rsa-sha2-512', 'rsa-sha2-256']:
            if rsa_variant in self.host_keys:
                # Use RSA key with SHA-1 signature
                return 'ssh-rsa', self.host_keys[rsa_variant]
    
    raise ValueError("No compatible host key algorithm")
```

### Authentication Handler

```python
class AuthenticationHandler:
    def __init__(self, server):
        self.server = server
        self.attempts = {}  # Track attempts per connection
        
    def handle_auth_request(self, transport, request):
        username = request.username
        method = request.method
        
        # Rate limiting
        conn_id = transport.get_connection_id()
        self.attempts[conn_id] = self.attempts.get(conn_id, 0) + 1
        
        if self.attempts[conn_id] > 3:
            transport.disconnect("Too many authentication attempts")
            return
        
        # Check authentication method
        if method == "publickey":
            return self._handle_publickey(transport, request)
        elif method == "password":
            return self._handle_password(transport, request)
        elif method == "keyboard-interactive":
            return self._handle_interactive(transport, request)
        else:
            # Send failure with available methods
            transport.send_userauth_failure(
                methods=["publickey", "password"],
                partial_success=False
            )
    
    def _handle_publickey(self, transport, request):
        # Check if key is authorized
        authorized_keys = self.server.get_authorized_keys(request.username)
        
        key_authorized = any(
            key.fingerprint == request.key.fingerprint 
            for key in authorized_keys
        )
        
        if not key_authorized:
            transport.send_userauth_failure(["publickey", "password"], False)
            return
        
        if not request.signature:
            # Client querying if key is acceptable
            transport.send_userauth_pk_ok(request.algorithm, request.key)
            return
        
        # Verify signature
        if self._verify_signature(transport, request):
            transport.send_userauth_success()
            self.attempts[transport.get_connection_id()] = 0
        else:
            transport.send_userauth_failure(["publickey", "password"], False)
```

## Channel Management

Channels are the heart of SSH's multiplexing capability. Understanding channel lifecycle and flow control is essential.

### Channel Lifecycle

```python
class ChannelManager:
    def __init__(self):
        self.channels = {}
        self.next_channel_id = 0
        self.lock = threading.Lock()
        
    def create_channel(self, channel_type, window_size=2097152, max_packet=32768):
        with self.lock:
            channel = Channel(
                local_id=self.next_channel_id,
                channel_type=channel_type,
                local_window=window_size,
                local_max_packet=max_packet
            )
            self.channels[channel.local_id] = channel
            self.next_channel_id += 1
            return channel
    
    def handle_channel_open(self, message):
        channel_type = message.channel_type
        remote_id = message.sender_channel
        remote_window = message.initial_window
        remote_max_packet = message.max_packet
        
        # Check if we accept this channel type
        if not self.accept_channel_type(channel_type):
            self.send_channel_open_failure(
                remote_id,
                SSH_OPEN_ADMINISTRATIVELY_PROHIBITED,
                "Channel type not supported"
            )
            return
        
        # Create local channel
        channel = self.create_channel(channel_type)
        channel.remote_id = remote_id
        channel.remote_window = remote_window
        channel.remote_max_packet = remote_max_packet
        
        # Send confirmation
        self.send_channel_open_confirmation(
            remote_id,
            channel.local_id,
            channel.local_window,
            channel.local_max_packet
        )
        
        # Handle channel-specific setup
        if channel_type == "session":
            self.setup_session_channel(channel)
        elif channel_type == "direct-tcpip":
            self.setup_port_forward(channel, message)
```

### Flow Control Implementation

```python
class ChannelFlowControl:
    def __init__(self, channel):
        self.channel = channel
        self.condition = threading.Condition()
        
    def send_data(self, data):
        """Send data respecting flow control window"""
        offset = 0
        
        while offset < len(data):
            with self.condition:
                # Wait for window space
                while self.channel.remote_window == 0:
                    self.condition.wait()
                
                # Calculate how much we can send
                chunk_size = min(
                    len(data) - offset,
                    self.channel.remote_window,
                    self.channel.remote_max_packet
                )
                
                # Send chunk
                chunk = data[offset:offset + chunk_size]
                self.send_channel_data(self.channel.remote_id, chunk)
                
                # Update window
                self.channel.remote_window -= chunk_size
                offset += chunk_size
    
    def handle_window_adjust(self, bytes_to_add):
        """Handle window adjustment from peer"""
        with self.condition:
            self.channel.remote_window += bytes_to_add
            self.condition.notify_all()  # Wake waiting senders
    
    def consume_data(self, data_length):
        """Update receive window after consuming data"""
        self.channel.local_window -= data_length
        
        # Send window adjustment if needed
        if self.channel.local_window < self.channel.initial_window // 2:
            adjustment = self.channel.initial_window - self.channel.local_window
            self.send_window_adjust(self.channel.remote_id, adjustment)
            self.channel.local_window = self.channel.initial_window
```

## Configuration Patterns

Proper SSH configuration balances security, compatibility, and usability.

### Client Configuration

Modern client configuration with compatibility fallbacks:

```ssh
# ~/.ssh/config

# Global secure defaults
Host *
    # Version 2 only
    Protocol 2
    
    # Key exchange algorithms (order matters)
    KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512,diffie-hellman-group14-sha256
    
    # Host key algorithms
    HostKeyAlgorithms ssh-ed25519,rsa-sha2-512,rsa-sha2-256,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521
    
    # Authentication key types
    PubkeyAcceptedAlgorithms ssh-ed25519,rsa-sha2-512,rsa-sha2-256,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521
    
    # Ciphers
    Ciphers chacha20-poly1305@openssh.com,aes128-gcm@openssh.com,aes256-gcm@openssh.com
    
    # MACs  
    MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com,umac-128-etm@openssh.com
    
    # Connection sharing
    ControlMaster auto
    ControlPath ~/.ssh/controlmasters/%r@%h:%p
    ControlPersist 10m
    
    # Security options
    StrictHostKeyChecking ask
    VerifyHostKeyDNS yes
    HashKnownHosts yes
    
    # Timeouts
    ServerAliveInterval 60
    ServerAliveCountMax 3

# Development servers (more convenient)
Host *.dev.example.com
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel ERROR

# Legacy system support
Host legacy-server.example.com
    # Add older algorithms only for this host
    KexAlgorithms +diffie-hellman-group14-sha1
    PubkeyAcceptedAlgorithms +ssh-rsa
    Ciphers +aes256-ctr,aes192-ctr,aes128-ctr

# Jump host configuration
Host production-*.example.com
    ProxyJump jumphost.example.com
    
# Specific key for GitHub
Host github.com
    IdentityFile ~/.ssh/github_ed25519
    IdentitiesOnly yes
```

### Server Configuration

Secure server configuration supporting multiple key types:

```ssh
# /etc/ssh/sshd_config

# Listen configuration
Port 22
ListenAddress 0.0.0.0
Protocol 2

# Host keys (multiple types for compatibility)
HostKey /etc/ssh/ssh_host_ed25519_key
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key

# Algorithm restrictions
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512,diffie-hellman-group14-sha256
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com,umac-128-etm@openssh.com

# Authentication
PubkeyAuthentication yes
PubkeyAcceptedKeyTypes ssh-ed25519,rsa-sha2-512,rsa-sha2-256,ecdsa-sha2-nistp256,ecdsa-sha2-nistp384,ecdsa-sha2-nistp521
PasswordAuthentication no
ChallengeResponseAuthentication no
PermitEmptyPasswords no

# Access control
PermitRootLogin no
AllowGroups ssh-users
DenyUsers nobody

# Security hardening
StrictModes yes
MaxAuthTries 3
MaxSessions 10
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2

# Logging
SyslogFacility AUTH
LogLevel VERBOSE

# Subsystems
Subsystem sftp /usr/lib/openssh/sftp-server

# Certificate authentication (if using)
TrustedUserCAKeys /etc/ssh/user_ca.pub
HostCertificate /etc/ssh/ssh_host_ed25519_key-cert.pub
```

### Per-User Configuration

Allow users to customize their environment safely:

```ssh
# /etc/ssh/sshd_config.d/user-overrides.conf

Match User developer
    PasswordAuthentication yes  # During transition
    
Match User ci-bot
    # Restrict CI user capabilities
    X11Forwarding no
    AllowTcpForwarding no
    PermitTTY no
    ForceCommand /usr/local/bin/ci-handler
    
Match Group backup-users
    # Restrict to SFTP only
    ForceCommand internal-sftp
    ChrootDirectory /backup/%u
    AllowTcpForwarding no
```

---

# Part 4: Advanced Implementation

## Binary Protocol Details

SSH uses a binary protocol with specific encodings for all data types. Understanding these is essential for protocol implementation.

### Packet Structure

Every SSH packet follows this format:

```
uint32    packet_length     # Excludes MAC and packet_length field itself
byte      padding_length    # 4-255 bytes
byte[n1]  payload          # n1 = packet_length - padding_length - 1
byte[n2]  random_padding   # n2 = padding_length
byte[m]   mac             # m = mac_length (outside encryption)
```

Implementation considerations:
- Minimum padding is 4 bytes
- Total packet length must be multiple of cipher block size (minimum 8)
- Maximum packet size is 35000 bytes (payload + padding)
- Padding should be random, not zeros

### Data Type Encodings

**Scalar Types**

```python
def encode_byte(value):
    return struct.pack('B', value)

def encode_boolean(value):
    return b'\x01' if value else b'\x00'

def encode_uint32(value):
    return struct.pack('>I', value)  # Big-endian

def encode_uint64(value):
    return struct.pack('>Q', value)  # Big-endian
```

**String Encoding**

```python
def encode_string(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return encode_uint32(len(data)) + data

def decode_string(buffer, offset):
    length = decode_uint32(buffer[offset:offset+4])
    data = buffer[offset+4:offset+4+length]
    return data, offset + 4 + length
```

**Multiple Precision Integers**

```python
def encode_mpint(value):
    if value == 0:
        return encode_uint32(0)
    
    # Convert to bytes, handling negative numbers
    negative = value < 0
    if negative:
        # Two's complement
        bytes_needed = (value.bit_length() + 8) // 8
        value = (1 << (bytes_needed * 8)) + value
    
    # Convert to bytes
    hex_str = format(value, 'x')
    if len(hex_str) % 2:
        hex_str = '0' + hex_str
    
    value_bytes = bytes.fromhex(hex_str)
    
    # Add leading zero if MSB is set for positive numbers
    if not negative and value_bytes[0] & 0x80:
        value_bytes = b'\x00' + value_bytes
    
    return encode_string(value_bytes)
```

**Name Lists**

```python
def encode_name_list(names):
    if isinstance(names, list):
        names = ','.join(names)
    return encode_string(names)

def decode_name_list(data):
    names_str = decode_string(data)
    return names_str.split(',') if names_str else []
```

### Message Number Ranges

SSH reserves specific message number ranges:

```python
# Transport layer
SSH_MSG_DISCONNECT = 1
SSH_MSG_IGNORE = 2
SSH_MSG_UNIMPLEMENTED = 3
SSH_MSG_DEBUG = 4
SSH_MSG_SERVICE_REQUEST = 5
SSH_MSG_SERVICE_ACCEPT = 6

# Algorithm negotiation
SSH_MSG_KEXINIT = 20
SSH_MSG_NEWKEYS = 21

# Key exchange (30-49 reserved)
SSH_MSG_KEXDH_INIT = 30
SSH_MSG_KEXDH_REPLY = 31

# User authentication (50-79)
SSH_MSG_USERAUTH_REQUEST = 50
SSH_MSG_USERAUTH_FAILURE = 51
SSH_MSG_USERAUTH_SUCCESS = 52
SSH_MSG_USERAUTH_BANNER = 53

# Connection protocol (80-127)
SSH_MSG_GLOBAL_REQUEST = 80
SSH_MSG_REQUEST_SUCCESS = 81
SSH_MSG_REQUEST_FAILURE = 82
SSH_MSG_CHANNEL_OPEN = 90
SSH_MSG_CHANNEL_OPEN_CONFIRMATION = 91
SSH_MSG_CHANNEL_OPEN_FAILURE = 92
SSH_MSG_CHANNEL_WINDOW_ADJUST = 93
SSH_MSG_CHANNEL_DATA = 94
SSH_MSG_CHANNEL_EXTENDED_DATA = 95
SSH_MSG_CHANNEL_EOF = 96
SSH_MSG_CHANNEL_CLOSE = 97
SSH_MSG_CHANNEL_REQUEST = 98
SSH_MSG_CHANNEL_SUCCESS = 99
SSH_MSG_CHANNEL_FAILURE = 100

# Local extensions (192-255)
SSH_MSG_LOCAL_MIN = 192
SSH_MSG_LOCAL_MAX = 255
```

## Performance Optimization

SSH performance depends on algorithm selection, connection patterns, and implementation efficiency.

### Algorithm Performance Impact

```python
# Relative performance measurements
ALGORITHM_PERFORMANCE = {
    # Key exchange (operations/second)
    'kex': {
        'curve25519-sha256': 8000,
        'ecdh-sha2-nistp256': 3000,
        'diffie-hellman-group14-sha256': 800,
        'diffie-hellman-group16-sha512': 200,
    },
    
    # Signatures (operations/second)
    'sign': {
        'ssh-ed25519': 10000,
        'ecdsa-sha2-nistp256': 3000,
        'rsa-sha2-256-2048': 500,
        'rsa-sha2-256-4096': 100,
    },
    
    # Ciphers (MB/second)
    'cipher': {
        'chacha20-poly1305@openssh.com': 950,
        'aes128-gcm@openssh.com': 850,  # With AES-NI
        'aes256-gcm@openssh.com': 750,  # With AES-NI
        'aes128-ctr': 450,
        'aes256-ctr': 380,
    }
}

def select_optimal_algorithms(hardware_features):
    algorithms = {}
    
    # Key exchange - balance security and speed
    algorithms['kex'] = [
        'curve25519-sha256',
        'curve25519-sha256@libssh.org',
    ]
    
    # Ciphers - check hardware support
    if hardware_features.has_aesni:
        algorithms['cipher'] = [
            'aes128-gcm@openssh.com',
            'chacha20-poly1305@openssh.com',
        ]
    else:
        algorithms['cipher'] = [
            'chacha20-poly1305@openssh.com',
            'aes128-gcm@openssh.com',
        ]
    
    return algorithms
```

### Connection Multiplexing

Reuse SSH connections to eliminate handshake overhead:

```python
class ConnectionMultiplexer:
    def __init__(self):
        self.connections = {}  # host:port -> connection
        self.lock = threading.Lock()
    
    def get_connection(self, host, port=22, username=None):
        key = f"{host}:{port}"
        
        with self.lock:
            if key in self.connections:
                conn = self.connections[key]
                if conn.is_alive():
                    return conn.create_channel()
            
            # Create new connection
            conn = self._create_connection(host, port, username)
            self.connections[key] = conn
            return conn.create_channel()
    
    def _create_connection(self, host, port, username):
        conn = SSHConnection()
        conn.connect(host, port)
        conn.authenticate(username)
        
        # Keep connection alive
        conn.set_keepalive(interval=60, count_max=3)
        
        return conn
```

### Parallel Operations

Leverage SSH's multiplexing for parallel operations:

```python
def parallel_command_execution(hosts, command):
    """Execute command on multiple hosts in parallel"""
    results = {}
    threads = []
    
    def execute_on_host(host):
        try:
            client = SSHClient()
            client.connect(host)
            
            # Use separate channels for parallel execution
            channel = client.open_channel()
            channel.exec_command(command)
            
            output = channel.read_all()
            exit_status = channel.get_exit_status()
            
            results[host] = {
                'output': output,
                'exit_status': exit_status
            }
        except Exception as e:
            results[host] = {'error': str(e)}
    
    # Start threads
    for host in hosts:
        thread = threading.Thread(target=execute_on_host, args=(host,))
        threads.append(thread)
        thread.start()
    
    # Wait for completion
    for thread in threads:
        thread.join()
    
    return results
```

### Buffer Management

Efficient buffer management reduces memory copies:

```python
class SSHBuffer:
    def __init__(self, data=None):
        self.buffer = bytearray(data) if data else bytearray()
        self.position = 0
    
    def write(self, data):
        self.buffer.extend(data)
    
    def read(self, length):
        if self.position + length > len(self.buffer):
            raise BufferError("Insufficient data")
        
        data = self.buffer[self.position:self.position + length]
        self.position += length
        return bytes(data)
    
    def read_string(self):
        length = struct.unpack('>I', self.read(4))[0]
        return self.read(length)
    
    def compact(self):
        """Remove consumed data"""
        if self.position > 0:
            self.buffer = self.buffer[self.position:]
            self.position = 0
    
    def __len__(self):
        return len(self.buffer) - self.position
```

## Extension Negotiation

RFC 8308 introduces extension negotiation to solve capability discovery.

### Implementation

```python
class ExtensionNegotiation:
    def __init__(self):
        self.supported_extensions = {
            'server-sig-algs': self._get_signature_algorithms(),
            'delay-compression': 'zlib@openssh.com,none',
            'no-flow-control': 'p@openssh.com',
            'elevation': 'y@example.com'  # Custom extension
        }
        
    def send_ext_info(self, transport):
        """Send extension information after NEW_KEYS"""
        extensions = []
        
        for name, value in self.supported_extensions.items():
            extensions.append(encode_string(name))
            extensions.append(encode_string(value))
        
        packet = bytearray()
        packet.append(SSH_MSG_EXT_INFO)
        packet.extend(encode_uint32(len(self.supported_extensions)))
        
        for ext in extensions:
            packet.extend(ext)
        
        transport.send_packet(bytes(packet))
    
    def handle_ext_info(self, packet):
        """Process extension information from peer"""
        nr_extensions = decode_uint32(packet)
        peer_extensions = {}
        
        for _ in range(nr_extensions):
            name = decode_string(packet)
            value = decode_string(packet)
            peer_extensions[name] = value
        
        # Process specific extensions
        if 'server-sig-algs' in peer_extensions:
            self._update_signature_algorithms(peer_extensions['server-sig-algs'])
        
        return peer_extensions
    
    def _get_signature_algorithms(self):
        """List signature algorithms we support"""
        return ','.join([
            'ssh-ed25519',
            'rsa-sha2-512',
            'rsa-sha2-256',
            'ecdsa-sha2-nistp256',
            'ecdsa-sha2-nistp384',
            'ecdsa-sha2-nistp521',
            'ssh-rsa'  # Still list for compatibility
        ])
```

### Using Extension Information

```python
def authenticate_with_extension_info(client, username, private_key):
    # Get server's supported signature algorithms
    server_sig_algs = client.extensions.get('server-sig-algs', '').split(',')
    
    if isinstance(private_key, RSAKey):
        # Choose best RSA signature algorithm
        for algo in ['rsa-sha2-512', 'rsa-sha2-256', 'ssh-rsa']:
            if algo in server_sig_algs:
                return client.auth_publickey(username, private_key, algo)
        
        # Server doesn't support any RSA algorithms
        raise AuthenticationError("No supported RSA signature algorithm")
    
    else:
        # Non-RSA keys have fixed algorithms
        key_algo = private_key.algorithm_name
        if key_algo not in server_sig_algs:
            raise AuthenticationError(f"Server doesn't support {key_algo}")
        
        return client.auth_publickey(username, private_key, key_algo)
```

## Certificate Authentication

SSH certificates provide centralized authentication without managing individual keys.

### Certificate Structure

```python
class SSHCertificate:
    def __init__(self):
        self.nonce = None
        self.public_key = None
        self.serial = 0
        self.cert_type = 1  # 1 = user, 2 = host
        self.key_id = ""
        self.valid_principals = []
        self.valid_after = 0
        self.valid_before = 0xFFFFFFFFFFFFFFFF
        self.critical_options = {}
        self.extensions = {}
        self.reserved = b''
        self.signature_key = None
        self.signature = None
    
    def encode(self):
        """Encode certificate for transmission"""
        cert = bytearray()
        
        # Certificate algorithm name
        if self.cert_type == 1:
            cert.extend(encode_string(f"{self.public_key.algorithm}-cert-v01@openssh.com"))
        else:
            cert.extend(encode_string(f"{self.public_key.algorithm}-cert-v00@openssh.com"))
        
        # Nonce
        cert.extend(encode_string(self.nonce))
        
        # Public key
        cert.extend(self.public_key.encode_bare())
        
        # Certificate data
        cert.extend(encode_uint64(self.serial))
        cert.extend(encode_uint32(self.cert_type))
        cert.extend(encode_string(self.key_id))
        
        # Valid principals
        principals_data = b''.join(encode_string(p) for p in self.valid_principals)
        cert.extend(encode_string(principals_data))
        
        # Validity period
        cert.extend(encode_uint64(self.valid_after))
        cert.extend(encode_uint64(self.valid_before))
        
        # Critical options
        cert.extend(self._encode_options(self.critical_options))
        
        # Extensions
        cert.extend(self._encode_options(self.extensions))
        
        # Reserved
        cert.extend(encode_string(self.reserved))
        
        # Signature key
        cert.extend(encode_string(self.signature_key.encode()))
        
        # Signature
        cert.extend(encode_string(self.signature))
        
        return bytes(cert)
```

### Certificate Generation

```python
class CertificateAuthority:
    def __init__(self, ca_key):
        self.ca_key = ca_key
        
    def sign_user_certificate(self, public_key, principals, **kwargs):
        cert = SSHCertificate()
        cert.nonce = os.urandom(32)
        cert.public_key = public_key
        cert.serial = kwargs.get('serial', int(time.time()))
        cert.cert_type = 1  # User certificate
        cert.key_id = kwargs.get('key_id', f"{principals[0]}_{cert.serial}")
        cert.valid_principals = principals
        
        # Validity period
        now = int(time.time())
        cert.valid_after = kwargs.get('valid_after', now)
        cert.valid_before = kwargs.get('valid_before', now + 365*24*3600)
        
        # Options
        cert.critical_options = kwargs.get('critical_options', {})
        cert.extensions = kwargs.get('extensions', {
            'permit-pty': '',
            'permit-user-rc': '',
            'permit-agent-forwarding': '',
            'permit-port-forwarding': ''
        })
        
        # Sign certificate
        cert.signature_key = self.ca_key.public_key()
        
        # Create signature
        tbs_cert = cert.encode_tbs()  # To-be-signed portion
        cert.signature = self.ca_key.sign(tbs_cert)
        
        return cert
    
    def sign_host_certificate(self, public_key, hostnames, **kwargs):
        cert = SSHCertificate()
        cert.nonce = os.urandom(32)
        cert.public_key = public_key
        cert.serial = kwargs.get('serial', int(time.time()))
        cert.cert_type = 2  # Host certificate
        cert.key_id = kwargs.get('key_id', hostnames[0])
        cert.valid_principals = hostnames
        
        # Validity period
        now = int(time.time())
        cert.valid_after = kwargs.get('valid_after', 0)
        cert.valid_before = kwargs.get('valid_before', 0xFFFFFFFFFFFFFFFF)
        
        # No critical options for host certificates
        cert.critical_options = {}
        cert.extensions = {}
        
        # Sign
        cert.signature_key = self.ca_key.public_key()
        tbs_cert = cert.encode_tbs()
        cert.signature = self.ca_key.sign(tbs_cert)
        
        return cert
```

### Certificate Validation

```python
def validate_certificate(cert, ca_keys, hostname=None, username=None):
    """Validate an SSH certificate"""
    
    # Check signature
    signature_valid = False
    for ca_key in ca_keys:
        if cert.signature_key.fingerprint == ca_key.fingerprint:
            if ca_key.verify(cert.encode_tbs(), cert.signature):
                signature_valid = True
                break
    
    if not signature_valid:
        raise ValueError("Certificate signature invalid")
    
    # Check validity period
    now = int(time.time())
    if now < cert.valid_after:
        raise ValueError("Certificate not yet valid")
    if now > cert.valid_before:
        raise ValueError("Certificate expired")
    
    # Check type
    if hostname and cert.cert_type != 2:
        raise ValueError("Not a host certificate")
    if username and cert.cert_type != 1:
        raise ValueError("Not a user certificate")
    
    # Check principal
    if hostname and hostname not in cert.valid_principals:
        # Check wildcards
        if not any(fnmatch.fnmatch(hostname, p) for p in cert.valid_principals):
            raise ValueError(f"Hostname {hostname} not in principals")
    
    if username and username not in cert.valid_principals:
        raise ValueError(f"Username {username} not in principals")
    
    # Check critical options
    for option, value in cert.critical_options.items():
        if option == 'force-command':
            # Enforced by server
            pass
        elif option == 'source-address':
            # Validate source address restriction
            if not validate_source_address(value):
                raise ValueError("Source address restriction violated")
        else:
            # Unknown critical option
            raise ValueError(f"Unknown critical option: {option}")
    
    return True
```

---

# Part 5: Operations and Migration

## Deployment Strategies

Deploying SSH securely requires planning for key distribution, algorithm support, and monitoring.

### Host Key Deployment

```python
# generate_host_keys.py
def generate_all_host_keys(hostname):
    """Generate complete set of host keys"""
    keys = {}
    
    # Ed25519 - Preferred
    print("Generating Ed25519 host key...")
    keys['ed25519'] = generate_ed25519_key()
    save_key(keys['ed25519'], f'/etc/ssh/ssh_host_ed25519_key')
    
    # ECDSA - Compatibility
    print("Generating ECDSA host key...")
    keys['ecdsa'] = generate_ecdsa_key('P-256')
    save_key(keys['ecdsa'], f'/etc/ssh/ssh_host_ecdsa_key')
    
    # RSA - Wide compatibility
    print("Generating RSA host key (3072-bit)...")
    keys['rsa'] = generate_rsa_key(3072)
    save_key(keys['rsa'], f'/etc/ssh/ssh_host_rsa_key')
    
    # Generate SSHFP records
    print("\nAdd these records to DNS:")
    for key_type, key in keys.items():
        print(generate_sshfp_record(hostname, key))
    
    return keys

def generate_sshfp_record(hostname, key):
    """Generate DNS SSHFP record"""
    algorithm_numbers = {
        'ssh-rsa': 1,
        'ssh-dss': 2,
        'ecdsa-sha2-nistp256': 3,
        'ssh-ed25519': 4
    }
    
    algo_num = algorithm_numbers.get(key.algorithm_name)
    fp_sha256 = hashlib.sha256(key.public_key_blob()).hexdigest()
    
    return f"{hostname}. IN SSHFP {algo_num} 2 {fp_sha256}"
```

### Automated Deployment

```bash
#!/bin/bash
# deploy_ssh_config.sh

# Configuration management with Ansible
cat > ssh_deployment.yml << 'EOF'
---
- name: Deploy secure SSH configuration
  hosts: all
  become: true
  
  tasks:
    - name: Generate host keys if missing
      openssh_keypair:
        path: "/etc/ssh/ssh_host_{{ item }}_key"
        type: "{{ item }}"
      with_items:
        - ed25519
        - rsa
        - ecdsa
    
    - name: Deploy sshd configuration
      template:
        src: sshd_config.j2
        dest: /etc/ssh/sshd_config
        owner: root
        group: root
        mode: '0644'
        validate: '/usr/sbin/sshd -t -f %s'
      notify: restart sshd
    
    - name: Deploy client configuration
      copy:
        src: ssh_config
        dest: /etc/ssh/ssh_config
        owner: root
        group: root
        mode: '0644'
    
    - name: Create SSH users group
      group:
        name: ssh-users
        state: present
    
    - name: Configure firewall
      ufw:
        rule: allow
        port: 22
        proto: tcp
        src: "{{ allowed_ssh_subnet }}"
    
  handlers:
    - name: restart sshd
      systemd:
        name: sshd
        state: restarted
        daemon_reload: true
EOF
```

### Key Distribution

Securely distribute user keys:

```python
class KeyDistribution:
    def __init__(self, ca_key=None):
        self.ca_key = ca_key
        
    def distribute_user_key(self, username, public_key, hosts):
        """Distribute user key to multiple hosts"""
        
        if self.ca_key:
            # Use certificates
            cert = self.ca_key.sign_user_certificate(
                public_key,
                principals=[username],
                valid_before=time.time() + 365*24*3600
            )
            
            # User keeps certificate locally
            return cert
        
        else:
            # Traditional authorized_keys distribution
            authorized_key_line = f"{public_key.to_authorized_keys()} {username}@deployed"
            
            for host in hosts:
                self._deploy_authorized_key(host, username, authorized_key_line)
    
    def _deploy_authorized_key(self, host, username, key_line):
        """Deploy key to remote host"""
        commands = [
            f"sudo mkdir -p ~{username}/.ssh",
            f"echo '{key_line}' | sudo tee -a ~{username}/.ssh/authorized_keys",
            f"sudo chown -R {username}:{username} ~{username}/.ssh",
            f"sudo chmod 700 ~{username}/.ssh",
            f"sudo chmod 644 ~{username}/.ssh/authorized_keys"
        ]
        
        # Execute via existing SSH access
        for cmd in commands:
            subprocess.run(['ssh', f'admin@{host}', cmd], check=True)
```

## Legacy System Migration

Migrating from legacy SSH configurations requires careful planning to avoid disrupting access.

### Assessment Phase

```python
# ssh_audit.py
def audit_ssh_algorithms(host, port=22):
    """Audit SSH server algorithm support"""
    
    # Custom SSH client that records negotiation
    client = SSHAuditor()
    client.connect(host, port)
    
    report = {
        'host': host,
        'version': client.server_version,
        'kex_algorithms': client.server_kex_algorithms,
        'host_key_algorithms': client.server_host_key_algorithms,
        'ciphers': client.server_ciphers,
        'macs': client.server_macs,
        'compression': client.server_compression,
        'issues': []
    }
    
    # Check for weak algorithms
    weak_kex = ['diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1']
    if any(k in report['kex_algorithms'] for k in weak_kex):
        report['issues'].append("Weak key exchange algorithms supported")
    
    weak_ciphers = ['3des-cbc', 'aes128-cbc', 'aes192-cbc', 'aes256-cbc']
    if any(c in report['ciphers'] for c in weak_ciphers):
        report['issues'].append("Weak ciphers supported")
    
    if 'ssh-rsa' in report['host_key_algorithms'] and \
       'rsa-sha2-256' not in report['host_key_algorithms']:
        report['issues'].append("Only SHA-1 RSA signatures supported")
    
    return report

def scan_network(subnet):
    """Scan network for SSH servers"""
    results = []
    
    for ip in ipaddress.ip_network(subnet):
        try:
            report = audit_ssh_algorithms(str(ip))
            results.append(report)
        except:
            pass  # Host not reachable or not SSH
    
    return results
```

### Migration Phases

**Phase 1: Discovery and Assessment**

```bash
# Log current algorithm usage
echo "LogLevel VERBOSE" >> /etc/ssh/sshd_config
systemctl reload sshd

# After 1 month, analyze usage
grep "SSH2_MSG_KEXINIT" /var/log/auth.log | \
    awk '{print $11}' | \
    sort | uniq -c | \
    sort -rn > algorithm_usage.txt

# Identify clients using weak algorithms
grep -E "(diffie-hellman-group1-sha1|3des-cbc|ssh-dss)" algorithm_usage.txt | \
    awk '{print $2}' | \
    sort -u > legacy_clients.txt
```

**Phase 2: Client Notification**

```python
def create_migration_banner():
    return """
================================================================================
                          SSH ALGORITHM MIGRATION NOTICE
    
Your SSH client is using deprecated cryptographic algorithms that will be
disabled on [DATE]. Please update your SSH client software.

Deprecated algorithms in use:
- Key Exchange: diffie-hellman-group1-sha1
- Cipher: 3des-cbc
- MAC: hmac-sha1

Recommended action:
1. Update your SSH client to the latest version
2. Or add these lines to ~/.ssh/config:
   
   Host this-server.example.com
       KexAlgorithms +diffie-hellman-group16-sha512
       Ciphers +aes256-ctr
       MACs +hmac-sha2-256

For assistance: email security@example.com
================================================================================
"""

# Deploy banner
with open('/etc/ssh/algorithm_migration_banner.txt', 'w') as f:
    f.write(create_migration_banner())

# Configure sshd to show banner
print("Banner /etc/ssh/algorithm_migration_banner.txt")
```

**Phase 3: Gradual Enforcement**

```python
class GradualMigration:
    def __init__(self, config_file='/etc/ssh/sshd_config'):
        self.config_file = config_file
        self.phases = [
            {
                'name': 'Permissive',
                'duration': 90,
                'config': {
                    'KexAlgorithms': '+diffie-hellman-group14-sha1',
                    'Ciphers': '+aes256-cbc,aes192-cbc,aes128-cbc',
                    'MACs': '+hmac-sha1'
                }
            },
            {
                'name': 'Transitional',
                'duration': 90,
                'config': {
                    'KexAlgorithms': '-diffie-hellman-group1-sha1',
                    'Ciphers': '-3des-cbc',
                    'MACs': '+hmac-sha1'
                }
            },
            {
                'name': 'Secure',
                'duration': None,
                'config': {
                    'KexAlgorithms': 'curve25519-sha256,diffie-hellman-group16-sha512',
                    'Ciphers': 'chacha20-poly1305@openssh.com,aes256-gcm@openssh.com',
                    'MACs': 'hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com'
                }
            }
        ]
    
    def apply_phase(self, phase_index):
        phase = self.phases[phase_index]
        print(f"Applying {phase['name']} phase")
        
        # Update configuration
        for directive, value in phase['config'].items():
            self._update_config(directive, value)
        
        # Reload SSH
        subprocess.run(['systemctl', 'reload', 'sshd'], check=True)
```

### Supporting Legacy Clients

When complete migration isn't possible:

```python
# Legacy compatibility wrapper
class LegacySSHProxy:
    """Proxy that upgrades legacy SSH connections"""
    
    def __init__(self, listen_port=2222, target_port=22):
        self.listen_port = listen_port
        self.target_port = target_port
        
    def handle_connection(self, client_socket):
        # Establish connection to real SSH server
        server_socket = socket.socket()
        server_socket.connect(('localhost', self.target_port))
        
        # Create transport with legacy algorithm support
        client_transport = LegacyTransport(client_socket)
        server_transport = ModernTransport(server_socket)
        
        # Bridge the connections
        bridge = TransportBridge(client_transport, server_transport)
        bridge.run()
```

## Monitoring and Troubleshooting

Effective SSH monitoring helps identify issues before they impact users.

### Connection Monitoring

```python
class SSHMonitor:
    def __init__(self, log_file='/var/log/auth.log'):
        self.log_file = log_file
        self.metrics = defaultdict(int)
        
    def parse_log_entry(self, line):
        patterns = {
            'connection': r'Connection from (\S+) port \d+',
            'auth_success': r'Accepted (\w+) for (\w+)',
            'auth_failure': r'Failed (\w+) for (?:invalid user )?(\w+)',
            'disconnect': r'Disconnected from (\S+) port \d+',
            'algorithm': r'kex: algorithm: (\S+)',
        }
        
        for metric, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                self.metrics[metric] += 1
                return metric, match.groups()
        
        return None, None
    
    def generate_report(self):
        return {
            'total_connections': self.metrics['connection'],
            'successful_auths': self.metrics['auth_success'],
            'failed_auths': self.metrics['auth_failure'],
            'auth_failure_rate': self.metrics['auth_failure'] / 
                                 (self.metrics['auth_success'] + self.metrics['auth_failure']),
            'algorithms_used': self.get_algorithm_distribution()
        }
```

### Performance Monitoring

```python
def monitor_ssh_performance():
    """Monitor SSH connection performance"""
    
    metrics = {
        'handshake_time': [],
        'auth_time': [],
        'total_time': []
    }
    
    def measure_connection(host):
        start = time.time()
        
        client = SSHClient()
        
        # Measure handshake
        handshake_start = time.time()
        client.connect(host, complete_handshake=True)
        handshake_time = time.time() - handshake_start
        
        # Measure authentication
        auth_start = time.time()
        client.authenticate()
        auth_time = time.time() - auth_start
        
        total_time = time.time() - start
        
        return {
            'handshake': handshake_time,
            'auth': auth_time,
            'total': total_time
        }
    
    # Monitor over time
    for _ in range(100):
        try:
            times = measure_connection('localhost')
            metrics['handshake_time'].append(times['handshake'])
            metrics['auth_time'].append(times['auth'])
            metrics['total_time'].append(times['total'])
        except:
            pass
        
        time.sleep(60)  # Every minute
    
    # Calculate statistics
    return {
        'handshake_avg': statistics.mean(metrics['handshake_time']),
        'handshake_p95': statistics.quantiles(metrics['handshake_time'], n=20)[18],
        'auth_avg': statistics.mean(metrics['auth_time']),
        'total_avg': statistics.mean(metrics['total_time'])
    }
```

### Troubleshooting Common Issues

```python
class SSHTroubleshooter:
    def diagnose_connection_failure(self, host, port=22, verbose=False):
        """Diagnose why SSH connection fails"""
        
        issues = []
        
        # Test TCP connectivity
        try:
            sock = socket.socket()
            sock.settimeout(5)
            sock.connect((host, port))
            sock.close()
        except socket.timeout:
            issues.append("Connection timeout - check firewall/network")
            return issues
        except ConnectionRefused:
            issues.append("Connection refused - SSH not running or wrong port")
            return issues
        
        # Test SSH protocol
        try:
            client = SSHClient()
            client.set_log_level('DEBUG' if verbose else 'INFO')
            client.connect(host, port)
        except VersionMismatch as e:
            issues.append(f"Protocol version mismatch: {e}")
        except AlgorithmNegotiationError as e:
            issues.append(f"No common algorithms: {e}")
            issues.append("Client algorithms: " + str(client.client_algorithms))
            issues.append("Server algorithms: " + str(client.server_algorithms))
        except HostKeyError as e:
            issues.append(f"Host key verification failed: {e}")
        except AuthenticationError as e:
            issues.append(f"Authentication failed: {e}")
        
        return issues
```

## Future-Proofing

Preparing for future SSH developments and cryptographic changes.

### Post-Quantum Readiness

```python
class PostQuantumSSH:
    """Prepare for post-quantum cryptography"""
    
    def __init__(self):
        self.pq_algorithms = {
            'kex': [
                'mlkem768x25519-sha256',
                'sntrup761x25519-sha512@openssh.com'
            ],
            'signature': [
                # Future PQ signature algorithms
            ]
        }
    
    def is_pq_ready(self, server_algorithms):
        """Check if server supports PQ algorithms"""
        return any(algo in server_algorithms['kex'] 
                   for algo in self.pq_algorithms['kex'])
    
    def upgrade_configuration(self, config):
        """Add PQ algorithms to configuration"""
        # Hybrid approach - PQ + classical
        config['KexAlgorithms'] = (
            self.pq_algorithms['kex'] + 
            config.get('KexAlgorithms', [])
        )
        return config
```

### Algorithm Agility

```python
class AlgorithmManager:
    """Manage algorithm transitions"""
    
    def __init__(self):
        self.algorithms = self.load_algorithm_database()
        
    def load_algorithm_database(self):
        return {
            'ssh-rsa': {
                'status': 'deprecated',
                'weakness': 'SHA-1 signatures',
                'replacement': ['rsa-sha2-256', 'rsa-sha2-512'],
                'removal_date': '2025-01-01'
            },
            'diffie-hellman-group14-sha1': {
                'status': 'legacy',
                'weakness': 'SHA-1 hash',
                'replacement': ['diffie-hellman-group14-sha256'],
                'removal_date': '2024-06-01'
            },
            'aes128-cbc': {
                'status': 'vulnerable',
                'weakness': 'CBC mode attacks',
                'replacement': ['aes128-ctr', 'aes128-gcm@openssh.com'],
                'removal_date': '2024-01-01'
            }
        }
    
    def check_algorithm_status(self, algorithm):
        info = self.algorithms.get(algorithm, {})
        
        if info.get('status') == 'deprecated':
            print(f"WARNING: {algorithm} is deprecated")
            print(f"Reason: {info['weakness']}")
            print(f"Use instead: {', '.join(info['replacement'])}")
            
            removal = datetime.fromisoformat(info['removal_date'])
            days_left = (removal - datetime.now()).days
            
            if days_left < 90:
                print(f"CRITICAL: Will be removed in {days_left} days!")
```

### Monitoring Best Practices

```yaml
# prometheus_ssh_metrics.yml
ssh_metrics:
  - metric: ssh_connection_total
    type: counter
    help: Total SSH connections
    labels:
      - source_ip
      - username
      - auth_method
  
  - metric: ssh_handshake_duration_seconds
    type: histogram
    help: SSH handshake duration
    buckets: [0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
  
  - metric: ssh_auth_failures_total
    type: counter
    help: SSH authentication failures
    labels:
      - username
      - auth_method
      - reason
  
  - metric: ssh_algorithm_usage
    type: counter
    help: Algorithm usage statistics
    labels:
      - algorithm_type
      - algorithm_name
  
  - metric: ssh_session_duration_seconds
    type: histogram
    help: SSH session duration
    buckets: [10, 60, 300, 1800, 3600, 7200, 14400]
```

---

# Technical Reference Index

## Algorithm Reference

### Key Exchange Algorithms
| Algorithm | Security Strength | Status | Notes |
|-----------|------------------|---------|--------|
| mlkem768x25519-sha256 | 192-bit | RECOMMENDED | Post-quantum hybrid |
| curve25519-sha256 | 128-bit | RECOMMENDED | Modern, fast |
| curve448-sha512 | 224-bit | OPTIONAL | Higher security |
| ecdh-sha2-nistp256 | 128-bit | RECOMMENDED | NIST standard |
| ecdh-sha2-nistp384 | 192-bit | OPTIONAL | NIST standard |
| ecdh-sha2-nistp521 | 256-bit | OPTIONAL | NIST standard |
| diffie-hellman-group16-sha512 | 128-bit | RECOMMENDED | 4096-bit MODP |
| diffie-hellman-group14-sha256 | 112-bit | REQUIRED | 2048-bit MODP |
| diffie-hellman-group14-sha1 | 112-bit | DEPRECATED | SHA-1 |
| diffie-hellman-group1-sha1 | 80-bit | FORBIDDEN | Too weak |

### Public Key Algorithms
| Algorithm | Key Size | Signature Size | Status |
|-----------|----------|----------------|---------|
| ssh-ed25519 | 32 bytes | 64 bytes | RECOMMENDED |
| ssh-ed448 | 57 bytes | 114 bytes | OPTIONAL |
| ecdsa-sha2-nistp256 | 64 bytes | ~72 bytes | RECOMMENDED |
| ecdsa-sha2-nistp384 | 96 bytes | ~104 bytes | OPTIONAL |
| ecdsa-sha2-nistp521 | 132 bytes | ~139 bytes | OPTIONAL |
| rsa-sha2-512 | Variable | Variable | RECOMMENDED |
| rsa-sha2-256 | Variable | Variable | RECOMMENDED |
| ssh-rsa | Variable | Variable | DEPRECATED |
| ssh-dss | 128 bytes | 40 bytes | FORBIDDEN |

### Ciphers
| Cipher | Key Size | Block Size | Status |
|--------|----------|------------|---------|
| chacha20-poly1305@openssh.com | 256-bit | N/A (stream) | RECOMMENDED |
| aes128-gcm@openssh.com | 128-bit | 128-bit | RECOMMENDED |
| aes256-gcm@openssh.com | 256-bit | 128-bit | OPTIONAL |
| aes128-ctr | 128-bit | 128-bit | RECOMMENDED |
| aes192-ctr | 192-bit | 128-bit | OPTIONAL |
| aes256-ctr | 256-bit | 128-bit | RECOMMENDED |
| aes128-cbc | 128-bit | 128-bit | DEPRECATED |
| 3des-cbc | 168-bit | 64-bit | FORBIDDEN |

### MAC Algorithms
| Algorithm | Output Size | Status |
|-----------|-------------|---------|
| hmac-sha2-256-etm@openssh.com | 32 bytes | RECOMMENDED |
| hmac-sha2-512-etm@openssh.com | 64 bytes | OPTIONAL |
| umac-128-etm@openssh.com | 16 bytes | RECOMMENDED |
| hmac-sha2-256 | 32 bytes | RECOMMENDED |
| hmac-sha2-512 | 64 bytes | OPTIONAL |
| hmac-sha1 | 20 bytes | DEPRECATED |
| hmac-md5 | 16 bytes | FORBIDDEN |

## Data Type Reference

### Type Encodings
| Type | Encoding | Example |
|------|----------|---------|
| byte | Single octet | 0x05 |
| boolean | 0x00 or 0x01 | 0x01 (true) |
| uint32 | 4 bytes, big-endian | 00 00 00 FF |
| uint64 | 8 bytes, big-endian | 00 00 00 00 00 00 00 FF |
| string | [length][data] | 00 00 00 04 74 65 73 74 |
| mpint | [length][two's complement] | 00 00 00 02 00 80 |
| name-list | Comma-separated string | "aes256-ctr,aes128-ctr" |

## Message Numbers

### Transport Layer (1-19)
```
SSH_MSG_DISCONNECT             1
SSH_MSG_IGNORE                 2
SSH_MSG_UNIMPLEMENTED          3
SSH_MSG_DEBUG                  4
SSH_MSG_SERVICE_REQUEST        5
SSH_MSG_SERVICE_ACCEPT         6
SSH_MSG_EXT_INFO               7
SSH_MSG_NEWCOMPRESS            8
```

### Key Exchange (20-29, 30-49)
```
SSH_MSG_KEXINIT                20
SSH_MSG_NEWKEYS                21
SSH_MSG_KEXDH_INIT             30
SSH_MSG_KEXDH_REPLY            31
SSH_MSG_KEX_ECDH_INIT          30
SSH_MSG_KEX_ECDH_REPLY         31
```

### Authentication (50-59, 60-79)
```
SSH_MSG_USERAUTH_REQUEST       50
SSH_MSG_USERAUTH_FAILURE       51
SSH_MSG_USERAUTH_SUCCESS       52
SSH_MSG_USERAUTH_BANNER        53
SSH_MSG_USERAUTH_PK_OK         60
SSH_MSG_USERAUTH_PASSWD_CHANGEREQ 60
SSH_MSG_USERAUTH_INFO_REQUEST  60
SSH_MSG_USERAUTH_INFO_RESPONSE 61
```

### Connection Protocol (80-127)
```
SSH_MSG_GLOBAL_REQUEST         80
SSH_MSG_REQUEST_SUCCESS        81
SSH_MSG_REQUEST_FAILURE        82
SSH_MSG_CHANNEL_OPEN           90
SSH_MSG_CHANNEL_OPEN_CONFIRMATION 91
SSH_MSG_CHANNEL_OPEN_FAILURE   92
SSH_MSG_CHANNEL_WINDOW_ADJUST  93
SSH_MSG_CHANNEL_DATA           94
SSH_MSG_CHANNEL_EXTENDED_DATA  95
SSH_MSG_CHANNEL_EOF            96
SSH_MSG_CHANNEL_CLOSE          97
SSH_MSG_CHANNEL_REQUEST        98
SSH_MSG_CHANNEL_SUCCESS        99
SSH_MSG_CHANNEL_FAILURE        100
```

## File Permissions

### Required Permissions
| Path | Permissions | Octal | Owner |
|------|------------|-------|--------|
| ~/.ssh/ | drwx------ | 0700 | user |
| ~/.ssh/id_* | -rw------- | 0600 | user |
| ~/.ssh/id_*.pub | -rw-r--r-- | 0644 | user |
| ~/.ssh/config | -rw------- | 0600 | user |
| ~/.ssh/authorized_keys | -rw-r--r-- | 0644 | user |
| ~/.ssh/known_hosts | -rw-r--r-- | 0644 | user |
| /etc/ssh/ssh_host_*_key | -rw------- | 0600 | root |
| /etc/ssh/ssh_host_*_key.pub | -rw-r--r-- | 0644 | root |
| /etc/ssh/sshd_config | -rw-r--r-- | 0644 | root |

## Configuration Directives

### Critical Client Options
```
StrictHostKeyChecking    ask|yes|no
VerifyHostKeyDNS         yes|no|ask
HashKnownHosts           yes|no
ControlMaster            auto|yes|no|autoask
ControlPath              path_specification
ControlPersist           yes|no|timeout
ServerAliveInterval      seconds
ServerAliveCountMax      count
```

### Critical Server Options
```
PermitRootLogin          yes|no|prohibit-password|forced-commands-only
PubkeyAuthentication     yes|no
PasswordAuthentication   yes|no
ChallengeResponseAuthentication yes|no
StrictModes              yes|no
MaxAuthTries             number
MaxSessions              number
ClientAliveInterval      seconds
ClientAliveCountMax      count
```

## Error Codes

### Disconnect Reason Codes
```
SSH_DISCONNECT_HOST_NOT_ALLOWED_TO_CONNECT    1
SSH_DISCONNECT_PROTOCOL_ERROR                 2
SSH_DISCONNECT_KEY_EXCHANGE_FAILED            3
SSH_DISCONNECT_RESERVED                       4
SSH_DISCONNECT_MAC_ERROR                      5
SSH_DISCONNECT_COMPRESSION_ERROR              6
SSH_DISCONNECT_SERVICE_NOT_AVAILABLE          7
SSH_DISCONNECT_PROTOCOL_VERSION_NOT_SUPPORTED 8
SSH_DISCONNECT_HOST_KEY_NOT_VERIFIABLE        9
SSH_DISCONNECT_CONNECTION_LOST                10
SSH_DISCONNECT_BY_APPLICATION                 11
SSH_DISCONNECT_TOO_MANY_CONNECTIONS           12
SSH_DISCONNECT_AUTH_CANCELLED_BY_USER         13
SSH_DISCONNECT_NO_MORE_AUTH_METHODS_AVAILABLE 14
SSH_DISCONNECT_ILLEGAL_USER_NAME              15
```

### Channel Open Failure Reasons
```
SSH_OPEN_ADMINISTRATIVELY_PROHIBITED          1
SSH_OPEN_CONNECT_FAILED                       2
SSH_OPEN_UNKNOWN_CHANNEL_TYPE                 3
SSH_OPEN_RESOURCE_SHORTAGE                    4
```

## SSHFP Record Format

### DNS Record Structure
```
hostname. IN SSHFP algorithm_number hash_type fingerprint
```

### Algorithm Numbers
| Number | Algorithm |
|--------|-----------|
| 1 | RSA |
| 2 | DSA (deprecated) |
| 3 | ECDSA |
| 4 | Ed25519 |
| 6 | Ed448 |

### Hash Types
| Number | Hash Algorithm |
|--------|----------------|
| 1 | SHA-1 (deprecated) |
| 2 | SHA-256 |

## Terminal Modes

### Common Terminal Mode Opcodes
```
TTY_OP_END         0    End of modes
VINTR              1    Interrupt character
VQUIT              2    Quit character
VERASE             3    Erase character
VKILL              4    Kill character
VEOF               5    End-of-file character
VEOL               6    End-of-line character
VEOL2              7    Additional end-of-line
VSTART             8    Start character
VSTOP              9    Stop character
VSUSP              10   Suspend character
VDSUSP             11   Delayed suspend
ECHO               53   Enable/disable echo
TTY_OP_ISPEED      128  Input speed
TTY_OP_OSPEED      129  Output speed
```
