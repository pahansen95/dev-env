"""Shell completion generation for dev-env CLI"""

import argparse
from pathlib import Path


def generate_bash_completion() -> str:
  """Generate bash completion script"""
  return """
# dev-env bash completion script

_dev_env_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Main commands
    local commands="up down list exec ssh logs attach"
    
    case $COMP_CWORD in
        1)
            # Complete main commands
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            ;;
        2)
            case "$prev" in
                up)
                    # Complete config files (.py or .json)
                    COMPREPLY=($(compgen -f -X '!*.@(py|json)' -- "$cur"))
                    ;;
                down|exec|ssh|logs|attach)
                    # Complete environment names
                    local envs=$(_dev_env_list_environments)
                    COMPREPLY=($(compgen -W "$envs" -- "$cur"))
                    ;;
            esac
            ;;
        3)
            case "${COMP_WORDS[1]}" in
                exec)
                    # For exec command, complete common commands
                    local exec_commands="bash sh python3 python ls cat cd pwd"
                    COMPREPLY=($(compgen -W "$exec_commands" -- "$cur"))
                    ;;
            esac
            ;;
    esac
    
    # Handle flags
    case "$prev" in
        --name)
            # Don't complete for name flag
            ;;
        --tail)
            # Complete common tail numbers
            COMPREPLY=($(compgen -W "10 50 100 500" -- "$cur"))
            ;;
        --state-dir)
            # Complete directories
            COMPREPLY=($(compgen -d -- "$cur"))
            ;;
    esac
}

_dev_env_list_environments() {
    # List existing environments using Python module
    python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    envs = state.list_environments()
    print(' '.join(envs.keys()))
except:
    pass
" 2>/dev/null
}

complete -F _dev_env_completion dev-env
complete -F _dev_env_completion 'python3 -m dev_env'

# Also register for direct Python module execution
complete -F _dev_env_completion 'python -m dev_env'
""".strip()


def generate_zsh_completion() -> str:
  """Generate zsh completion script"""
  return """
#compdef dev-env python3 -m dev_env python -m dev_env

# dev-env zsh completion script

_dev_env() {
    local context state state_descr line
    typeset -A opt_args
    
    _arguments -C \
        '--version[Show version]' \
        '--state-dir[Directory for storing environment state]:state directory:_directories' \
        '1: :_dev_env_commands' \
        '*:: :->args' \
        && return 0
    
    case $state in
        args)
            case $words[1] in
                up)
                    _arguments \
                        '--name[Override environment name]:name:' \
                        '*:config file:_files -g "*.py *.json"'
                    ;;
                down)
                    _arguments \
                        '--volumes[Also remove volumes]' \
                        '*:environment name:_dev_env_environments'
                    ;;
                list)
                    # No additional arguments
                    ;;
                exec)
                    _arguments \
                        '1:environment name:_dev_env_environments' \
                        '*:command:_command_names'
                    ;;
                ssh)
                    _arguments \
                        '1:environment name:_dev_env_environments' \
                        '*:ssh args:'
                    ;;
                logs)
                    _arguments \
                        '-f[Follow log output]' \
                        '--follow[Follow log output]' \
                        '--tail[Number of lines to show]:lines:(10 50 100 500)' \
                        '*:environment name:_dev_env_environments'
                    ;;
                attach)
                    _arguments \
                        '*:environment name:_dev_env_environments'
                    ;;
            esac
            ;;
    esac
}

_dev_env_commands() {
    local commands=(
        'up:Create and start an environment'
        'down:Stop and remove an environment'
        'list:List all environments'
        'exec:Execute command in environment'
        'ssh:SSH into environment'
        'logs:Show container logs'
        'attach:Attach to environment main process'
    )
    _describe 'commands' commands
}

_dev_env_environments() {
    local envs
    envs=(${(f)"$(python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    envs = state.list_environments()
    for name in envs.keys():
        print(name)
except:
    pass
" 2>/dev/null)"})
    _describe 'environments' envs
}

_dev_env "$@"
""".strip()


def generate_fish_completion() -> str:
  """Generate fish completion script"""
  return """
# dev-env fish completion script

# Helper function to list environments
function __dev_env_list_environments
    python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    envs = state.list_environments()
    for name in envs.keys():
        print(name)
except:
    pass
" 2>/dev/null
end

# Main command completions
complete -c dev-env -f
complete -c dev-env -n "__fish_use_subcommand" -a "up" -d "Create and start an environment"
complete -c dev-env -n "__fish_use_subcommand" -a "down" -d "Stop and remove an environment"
complete -c dev-env -n "__fish_use_subcommand" -a "list" -d "List all environments"
complete -c dev-env -n "__fish_use_subcommand" -a "exec" -d "Execute command in environment"
complete -c dev-env -n "__fish_use_subcommand" -a "ssh" -d "SSH into environment"
complete -c dev-env -n "__fish_use_subcommand" -a "logs" -d "Show container logs"
complete -c dev-env -n "__fish_use_subcommand" -a "attach" -d "Attach to environment main process"

# Global options
complete -c dev-env -l version -d "Show version"
complete -c dev-env -l state-dir -d "Directory for storing environment state" -r

# up command
complete -c dev-env -n "__fish_seen_subcommand_from up" -l name -d "Override environment name" -r
complete -c dev-env -n "__fish_seen_subcommand_from up" -F -a "*.py *.json" -d "Configuration file"

# down command
complete -c dev-env -n "__fish_seen_subcommand_from down" -l volumes -d "Also remove volumes"
complete -c dev-env -n "__fish_seen_subcommand_from down" -f -a "(__dev_env_list_environments)" -d "Environment name"

# exec command
complete -c dev-env -n "__fish_seen_subcommand_from exec; and test (count (commandline -opc)) -eq 2" -f -a "(__dev_env_list_environments)" -d "Environment name"
complete -c dev-env -n "__fish_seen_subcommand_from exec; and test (count (commandline -opc)) -gt 2" -a "bash sh python3 python ls cat cd pwd" -d "Command to execute"

# ssh command
complete -c dev-env -n "__fish_seen_subcommand_from ssh" -f -a "(__dev_env_list_environments)" -d "Environment name"

# logs command
complete -c dev-env -n "__fish_seen_subcommand_from logs" -f -a "(__dev_env_list_environments)" -d "Environment name"
complete -c dev-env -n "__fish_seen_subcommand_from logs" -s f -l follow -d "Follow log output"
complete -c dev-env -n "__fish_seen_subcommand_from logs" -l tail -d "Number of lines to show" -r -a "10 50 100 500"

# attach command
complete -c dev-env -n "__fish_seen_subcommand_from attach" -f -a "(__dev_env_list_environments)" -d "Environment name"

# Also complete for python -m dev_env
complete -c python3 -n "contains -- '-m' (commandline -opc); and contains -- 'dev_env' (commandline -opc)" -w dev-env
complete -c python -n "contains -- '-m' (commandline -opc); and contains -- 'dev_env' (commandline -opc)" -w dev-env
""".strip()


def cmd_completion(args: argparse.Namespace) -> int:
  """Generate shell completion scripts"""
  shell = args.shell.lower()

  if shell == "bash":
    content = generate_bash_completion()
    filename = "dev-env-completion.bash"
  elif shell == "zsh":
    content = generate_zsh_completion()
    filename = "_dev-env"
  elif shell == "fish":
    content = generate_fish_completion()
    filename = "dev-env.fish"
  else:
    print(f"Unsupported shell: {shell}")
    return 1

  output_file = args.output
  if not output_file:
    # Print to stdout if no output file specified
    print(content)
    return 0

  # Write to file
  output_path = Path(output_file)
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(content)

  print(f"Shell completion script generated: {output_path}")

  # Print installation instructions
  print("\nTo install the completion script:")

  if shell == "bash":
    print("  # Copy to bash completion directory:")
    print(f"  sudo cp {output_path} /etc/bash_completion.d/")
    print("  # Or source in your ~/.bashrc:")
    print(f"  echo 'source {output_path.absolute()}' >> ~/.bashrc")
  elif shell == "zsh":
    print("  # Copy to zsh completion directory:")
    print(f"  cp {output_path} ~/.zsh/completions/ && fpath=(~/.zsh/completions $fpath)")
    print("  # Or if using oh-my-zsh:")
    print(f"  cp {output_path} ~/.oh-my-zsh/completions/")
  elif shell == "fish":
    print("  # Copy to fish completion directory:")
    print(f"  cp {output_path} ~/.config/fish/completions/")

  print("\nRestart your shell or source your shell configuration to enable completions.")

  return 0


def add_completion_parser(subparsers) -> None:
  """Add completion command to CLI parser"""
  completion_parser = subparsers.add_parser("completion", help="Generate shell completion scripts")
  completion_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell to generate completion for")
  completion_parser.add_argument("-o", "--output", type=Path, help="Output file (prints to stdout if not specified)")
  completion_parser.set_defaults(func=cmd_completion)
