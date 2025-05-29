"""Utility functions using stdlib only"""

import subprocess
import shutil
import tempfile
import socket
from pathlib import Path
from typing import List, Optional, Tuple, Dict
import hashlib
import time


def check_docker_available() -> bool:
  """Check if Docker daemon is accessible"""
  # Check socket exists
  docker_socket = Path("/var/run/docker.sock")
  if not docker_socket.exists():
    return False

  # Try to connect
  try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(docker_socket))
    sock.close()
    return True
  except Exception:
    return False


def generate_container_name(env_name: str) -> str:
  """Generate a unique container name"""
  timestamp = int(time.time())
  hash_input = f"{env_name}-{timestamp}".encode()
  hash_suffix = hashlib.sha256(hash_input).hexdigest()[:8]
  return f"devenv-{env_name}-{hash_suffix}"


def run_command(cmd: List[str], cwd: Optional[Path] = None, capture_output: bool = False) -> Tuple[int, str, str]:
  """Run a command and return exit code, stdout, stderr"""
  if capture_output:
    result = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout, result.stderr
  else:
    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode, "", ""


def clone_git_repository(url: str, target: Path, branch: str = "main", shallow: bool = True) -> None:
  """Clone a git repository"""
  if not shutil.which("git"):
    raise RuntimeError("Git is not installed")

  cmd = ["git", "clone"]
  if shallow:
    cmd.extend(["--depth", "1"])
  if branch:
    cmd.extend(["--branch", branch])
  cmd.extend([url, str(target)])

  returncode, _, stderr = run_command(cmd, capture_output=True)
  if returncode != 0:
    raise RuntimeError(f"Failed to clone repository: {stderr}")


def generate_ssh_key_pair() -> Tuple[str, str]:
  """Generate an SSH key pair (private, public)"""
  if not shutil.which("ssh-keygen"):
    raise RuntimeError("ssh-keygen is not installed")

  with tempfile.TemporaryDirectory() as tmpdir:
    key_path = Path(tmpdir) / "id_rsa"

    cmd = [
      "ssh-keygen",
      "-t",
      "rsa",
      "-b",
      "2048",
      "-f",
      str(key_path),
      "-N",
      "",  # No passphrase
      "-C",
      "dev-env@localhost",
    ]

    returncode, _, stderr = run_command(cmd, capture_output=True)
    if returncode != 0:
      raise RuntimeError(f"Failed to generate SSH key: {stderr}")

    private_key = key_path.read_text()
    public_key = key_path.with_suffix(".pub").read_text()

    return private_key, public_key


def hash_file(file_path: Path) -> str:
  """Calculate SHA256 hash of a file"""
  sha256 = hashlib.sha256()
  with open(file_path, "rb") as f:
    for chunk in iter(lambda: f.read(8192), b""):
      sha256.update(chunk)
  return sha256.hexdigest()


def hash_config(config_dict: dict) -> str:
  """Calculate hash of configuration dictionary"""
  # Sort keys for consistent hashing
  import json

  config_str = json.dumps(config_dict, sort_keys=True)
  return hashlib.sha256(config_str.encode()).hexdigest()


def format_size(size_bytes: int) -> str:
  """Format bytes as human-readable size"""
  for unit in ["B", "KB", "MB", "GB", "TB"]:
    if size_bytes < 1024.0:
      return f"{size_bytes:.1f} {unit}"
    size_bytes /= 1024.0
  return f"{size_bytes:.1f} PB"


def parse_port_mapping(port_str: str) -> Tuple[int, int]:
  """Parse port mapping string (e.g., '8080:80' or '80')"""
  parts = port_str.split(":")
  if len(parts) == 1:
    port = int(parts[0])
    return port, port
  elif len(parts) == 2:
    return int(parts[0]), int(parts[1])
  else:
    raise ValueError(f"Invalid port mapping: {port_str}")


def ensure_ssh_config(container_name: str, port: int) -> None:
  """Add SSH config entry for container"""
  ssh_dir = Path.home() / ".ssh"
  ssh_dir.mkdir(mode=0o700, exist_ok=True)

  config_file = ssh_dir / "config"
  config_entry = f"""
Host devenv-{container_name}
    HostName localhost
    Port {port}
    User root
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
"""

  # Check if entry already exists
  if config_file.exists():
    existing = config_file.read_text()
    if f"Host devenv-{container_name}" in existing:
      return

  # Append entry
  with open(config_file, "a") as f:
    f.write(config_entry)


def remove_ssh_config(container_name: str) -> None:
  """Remove SSH config entry for container"""
  config_file = Path.home() / ".ssh" / "config"
  if not config_file.exists():
    return

  lines = config_file.read_text().splitlines()
  new_lines = []
  skip = False

  for line in lines:
    if line.strip() == f"Host devenv-{container_name}":
      skip = True
    elif skip and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
      skip = False

    if not skip:
      new_lines.append(line)

  config_file.write_text("\n".join(new_lines))


def wait_for_port(host: str, port: int, timeout: int = 30) -> bool:
  """Wait for a port to become available"""
  start_time = time.time()

  while time.time() - start_time < timeout:
    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(1)
      result = sock.connect_ex((host, port))
      sock.close()

      if result == 0:
        return True
    except Exception:
      pass

    time.sleep(0.5)

  return False


def setup_ssh_server(docker_client, container_id: str) -> None:
  """Setup SSH server in container"""

  # Detect package manager and install OpenSSH server
  output, exit_code = docker_client.exec_run(container_id, ["which", "apt-get"])
  if exit_code == 0:
    # Debian/Ubuntu
    docker_client.exec_run(container_id, ["apt-get", "update"])
    docker_client.exec_run(container_id, ["apt-get", "install", "-y", "openssh-server"])
  else:
    output, exit_code = docker_client.exec_run(container_id, ["which", "yum"])
    if exit_code == 0:
      # RHEL/CentOS
      docker_client.exec_run(container_id, ["yum", "install", "-y", "openssh-server"])
    else:
      output, exit_code = docker_client.exec_run(container_id, ["which", "apk"])
      if exit_code == 0:
        # Alpine
        docker_client.exec_run(container_id, ["apk", "add", "openssh"])
      else:
        raise RuntimeError("Could not detect package manager for SSH installation")

  # Create SSH directories
  docker_client.exec_run(container_id, ["mkdir", "-p", "/var/run/sshd", "/root/.ssh"])
  docker_client.exec_run(container_id, ["chmod", "700", "/root/.ssh"])

  # Generate host keys
  docker_client.exec_run(container_id, ["ssh-keygen", "-A"])

  # Configure SSH daemon
  sshd_config = """
Port 22
Protocol 2
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_dsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key
UsePrivilegeSeparation yes
KeyRegenerationInterval 3600
ServerKeyBits 1024
SyslogFacility AUTH
LogLevel INFO
LoginGraceTime 120
PermitRootLogin yes
StrictModes yes
RSAAuthentication yes
PubkeyAuthentication yes
IgnoreRhosts yes
RhostsRSAAuthentication no
HostbasedAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no
PasswordAuthentication no
X11Forwarding yes
X11DisplayOffset 10
PrintMotd no
PrintLastLog yes
TCPKeepAlive yes
AcceptEnv LANG LC_*
Subsystem sftp /usr/lib/openssh/sftp-server
UsePAM yes
""".strip()

  # Write SSH config
  docker_client.exec_run(container_id, ["sh", "-c", f"echo '{sshd_config}' > /etc/ssh/sshd_config"])


def inject_ssh_key(docker_client, container_id: str, public_key: str) -> None:
  """Inject SSH public key into container"""
  # Write authorized_keys
  docker_client.exec_run(container_id, ["sh", "-c", f"echo '{public_key.strip()}' > /root/.ssh/authorized_keys"])
  docker_client.exec_run(container_id, ["chmod", "600", "/root/.ssh/authorized_keys"])


def start_ssh_daemon(docker_client, container_id: str) -> None:
  """Start SSH daemon in container"""
  # Start SSH daemon
  output, exit_code = docker_client.exec_run(container_id, ["/usr/sbin/sshd", "-D"], user="root")
  if exit_code != 0:
    # Try alternative path
    docker_client.exec_run(container_id, ["/usr/sbin/sshd"])


def get_host_ssh_key() -> str:
  """Get host's SSH public key"""
  ssh_dir = Path.home() / ".ssh"

  # Try common key files
  for key_file in ["id_rsa.pub", "id_ed25519.pub", "id_ecdsa.pub"]:
    key_path = ssh_dir / key_file
    if key_path.exists():
      return key_path.read_text().strip()

  # Generate new key if none found
  print("No SSH key found, generating new key pair...")
  private_key, public_key = generate_ssh_key_pair()

  # Save to default location
  ssh_dir.mkdir(mode=0o700, exist_ok=True)
  (ssh_dir / "id_rsa").write_text(private_key)
  (ssh_dir / "id_rsa").chmod(0o600)
  (ssh_dir / "id_rsa.pub").write_text(public_key)
  (ssh_dir / "id_rsa.pub").chmod(0o644)

  return public_key.strip()


def setup_git_in_container(
  docker_client, container_id: str, git_config, host_git_config: Optional[Dict[str, str]] = None
) -> None:
  """Setup Git and clone repository in container"""
  # Install git if not present
  output, exit_code = docker_client.exec_run(container_id, ["which", "git"])
  if exit_code != 0:
    # Detect package manager and install git
    output, exit_code = docker_client.exec_run(container_id, ["which", "apt-get"])
    if exit_code == 0:
      # Debian/Ubuntu
      docker_client.exec_run(container_id, ["apt-get", "update"])
      docker_client.exec_run(container_id, ["apt-get", "install", "-y", "git"])
    else:
      output, exit_code = docker_client.exec_run(container_id, ["which", "yum"])
      if exit_code == 0:
        # RHEL/CentOS
        docker_client.exec_run(container_id, ["yum", "install", "-y", "git"])
      else:
        output, exit_code = docker_client.exec_run(container_id, ["which", "apk"])
        if exit_code == 0:
          # Alpine
          docker_client.exec_run(container_id, ["apk", "add", "git"])

  # Configure git identity from host if available
  if host_git_config:
    if "user.name" in host_git_config:
      docker_client.exec_run(container_id, ["git", "config", "--global", "user.name", host_git_config["user.name"]])
    if "user.email" in host_git_config:
      docker_client.exec_run(container_id, ["git", "config", "--global", "user.email", host_git_config["user.email"]])

  # Create workspace directory
  docker_client.exec_run(container_id, ["mkdir", "-p", git_config.path])

  # Clone repository
  clone_cmd = ["git", "clone"]
  if git_config.shallow:
    clone_cmd.extend(["--depth", "1"])
  if git_config.branch and git_config.branch != "main":
    clone_cmd.extend(["--branch", git_config.branch])
  clone_cmd.extend([git_config.url, git_config.path])

  output, exit_code = docker_client.exec_run(container_id, clone_cmd)
  if exit_code != 0:
    raise RuntimeError(f"Failed to clone repository: {output.decode('utf-8', errors='replace')}")


def get_host_git_config() -> Dict[str, str]:
  """Get host Git configuration"""
  config = {}

  try:
    # Get user.name
    result = subprocess.run(["git", "config", "--global", "user.name"], capture_output=True, text=True)
    if result.returncode == 0:
      config["user.name"] = result.stdout.strip()
  except Exception:
    pass

  try:
    # Get user.email
    result = subprocess.run(["git", "config", "--global", "user.email"], capture_output=True, text=True)
    if result.returncode == 0:
      config["user.email"] = result.stdout.strip()
  except Exception:
    pass

  return config
