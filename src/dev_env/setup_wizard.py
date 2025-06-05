"""Interactive setup wizard for development environments."""

from typing import Dict, Any, Optional

from dev_env.config_detector import ConfigDetector
from dev_env.context import Context


class SetupWizard:
  """Interactive wizard for creating development environment configurations."""

  def __init__(self):
    """Initialize the setup wizard."""
    self.detector = ConfigDetector()

  def run(self, context: Context) -> Dict[str, Any]:
    """
    Run the interactive setup wizard.

    Returns configuration data that can be saved to dev-env.yaml.
    """
    print("\n🧙 Development Environment Setup Wizard")
    print("=" * 40)

    # Step 1: Detect existing configuration
    detected = self.detector.detect(context.path)

    if detected:
      print(f"\n✨ Detected: {detected['type']} configuration")
      if detected["type"] == "language":
        print(f"   Language: {detected['language']}")
        print(f"   Suggested image: {detected['suggested_image']}")
      elif detected["type"] == "dockerfile":
        print(f"   Base image: {detected.get('base_image', 'unknown')}")

      use_detected = self._prompt_yes_no("Use detected configuration?", default=True)
      if use_detected:
        return self._create_config_from_detection(context, detected)

    # Step 2: Manual configuration
    print("\n📝 Manual Configuration")

    # Get base image
    image = self._prompt_string(
      "Base image", default=detected.get("suggested_image", "ubuntu:22.04") if detected else "ubuntu:22.04"
    )

    # Get shell
    shell = self._prompt_choice("Shell", choices=["/bin/bash", "/bin/sh", "/bin/zsh"], default="/bin/bash")

    # Get working directory
    workdir = self._prompt_string("Working directory", default="/workspace")

    # Ask about common features
    print("\n🔧 Features")

    features = {}
    if self._prompt_yes_no("Enable Git?", default=True):
      features["git"] = True

    if self._prompt_yes_no("Enable SSH access?", default=False):
      features["ssh"] = True

    if self._prompt_yes_no("Mount current directory?", default=True):
      features["mount_workspace"] = True

    # Language-specific setup
    if detected and detected["type"] == "language":
      features["language"] = detected["language"]
      features["language_files"] = detected.get("files", {})

    # Step 3: Create configuration
    config = self._create_config(
      context=context, image=image, shell=shell, workdir=workdir, features=features, detected=detected
    )

    print("\n✅ Configuration created!")
    return config

  def _create_config_from_detection(self, context: Context, detected: Dict[str, Any]) -> Dict[str, Any]:
    """Create configuration from detected settings."""
    config = {
      "name": context.name,
      "environment": {
        "USER": "dev",
        "WORKDIR": "/workspace",
      },
    }

    if detected["type"] == "language":
      config["image"] = detected["suggested_image"]
      config["shell"] = "/bin/bash"

      # Add language-specific setup
      if detected["language"] == "python":
        config["postCreateCommand"] = (
          "pip install -r requirements.txt" if detected["files"].get("requirements") else None
        )
      elif detected["language"] == "nodejs":
        config["postCreateCommand"] = "npm install"

    elif detected["type"] == "dockerfile":
      config["build"] = {"dockerfile": detected["path"]}
      config["shell"] = "/bin/bash"

    elif detected["type"] == "devcontainer":
      # Convert devcontainer format
      config["image"] = detected.get("image", "ubuntu:22.04")
      if detected.get("dockerfile"):
        config["build"] = {"dockerfile": detected["dockerfile"]}
      config["postCreateCommand"] = detected.get("postCreateCommand")
      config["user"] = detected.get("remoteUser", "1000:1000")

    # Always mount workspace
    config["mounts"] = [{"source": ".", "target": "/workspace", "type": "bind"}]

    return config

  def _create_config(
    self,
    context: Context,
    image: str,
    shell: str,
    workdir: str,
    features: Dict[str, Any],
    detected: Optional[Dict[str, Any]],
  ) -> Dict[str, Any]:
    """Create configuration from wizard inputs."""
    config = {
      "name": context.name,
      "image": image,
      "shell": shell,
      "environment": {
        "USER": "dev",
        "WORKDIR": workdir,
      },
    }

    # Add mounts
    mounts = []
    if features.get("mount_workspace"):
      mounts.append({"source": ".", "target": workdir, "type": "bind"})

    if mounts:
      config["mounts"] = mounts

    # Add SSH if requested
    if features.get("ssh"):
      config["ssh"] = {
        "enabled": True,
        "port": 22,
      }
      config["ports"] = {"22": {"HostPort": 2222}}

    # Add language-specific commands
    if features.get("language") == "python":
      if detected and detected["files"].get("requirements"):
        config["postCreateCommand"] = "pip install -r requirements.txt"
    elif features.get("language") == "nodejs":
      config["postCreateCommand"] = "npm install"

    return config

  def _prompt_yes_no(self, prompt: str, default: bool = False) -> bool:
    """Prompt for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    while True:
      response = input(f"{prompt} [{default_str}]: ").strip().lower()
      if not response:
        return default
      if response in ("y", "yes"):
        return True
      if response in ("n", "no"):
        return False
      print("Please answer 'y' or 'n'")

  def _prompt_string(self, prompt: str, default: str = "") -> str:
    """Prompt for string input."""
    response = input(f"{prompt} [{default}]: ").strip()
    return response if response else default

  def _prompt_choice(self, prompt: str, choices: list[str], default: str) -> str:
    """Prompt for choice from list."""
    print(f"\n{prompt}:")
    for i, choice in enumerate(choices, 1):
      marker = " *" if choice == default else ""
      print(f"  {i}. {choice}{marker}")

    while True:
      response = input(f"Choice [1-{len(choices)}]: ").strip()
      if not response:
        return default

      try:
        idx = int(response) - 1
        if 0 <= idx < len(choices):
          return choices[idx]
      except ValueError:
        pass

      print(f"Please enter a number between 1 and {len(choices)}")
