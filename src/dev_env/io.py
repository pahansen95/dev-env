"""Input/output abstractions for testing and interactive use."""

from typing import Protocol, List


class InputProvider(Protocol):
  """Protocol for providing user input."""

  def get_input(self, prompt: str) -> str:
    """Get string input from user."""
    ...

  def get_yes_no(self, prompt: str, default: bool = False) -> bool:
    """Get yes/no input from user."""
    ...

  def get_choice(self, prompt: str, choices: List[str], default: str) -> str:
    """Get choice from list of options."""
    ...


class StdinInputProvider:
  """Real input provider that reads from stdin."""

  def get_input(self, prompt: str) -> str:
    """Get string input from user."""
    return input(prompt).strip()

  def get_yes_no(self, prompt: str, default: bool = False) -> bool:
    """Get yes/no input from user."""
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

  def get_choice(self, prompt: str, choices: List[str], default: str) -> str:
    """Get choice from list of options."""
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


class MockInputProvider:
  """Mock input provider for testing."""

  def __init__(self, responses: List[str] = None):
    """Initialize with predefined responses."""
    self.responses = responses or []
    self.response_index = 0

  def get_input(self, prompt: str) -> str:
    """Return next predefined response."""
    if self.response_index < len(self.responses):
      response = self.responses[self.response_index]
      self.response_index += 1
      return response
    return ""

  def get_yes_no(self, prompt: str, default: bool = False) -> bool:
    """Return yes/no based on next response."""
    response = self.get_input(prompt).lower()
    if response in ("y", "yes", "true", "1"):
      return True
    elif response in ("n", "no", "false", "0"):
      return False
    return default

  def get_choice(self, prompt: str, choices: List[str], default: str) -> str:
    """Return choice based on next response."""
    response = self.get_input(prompt)
    if not response:
      return default

    # Try to parse as number (1-based index)
    try:
      idx = int(response) - 1
      if 0 <= idx < len(choices):
        return choices[idx]
    except ValueError:
      pass

    # Try to match exact choice
    if response in choices:
      return response

    return default
