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
    local commands="work stop run status shell context-create context-resolve context-list env-create env-start env-stop env-status plumbing-exec plumbing-attach completion"

    case $COMP_CWORD in
        1)
            # Complete main commands
            COMPREPLY=($(compgen -W "$commands" -- "$cur"))
            ;;
        2)
            case "$prev" in
                run|plumbing-exec)
                    # Complete common commands
                    local exec_commands="bash sh python3 python ls cat cd pwd"
                    COMPREPLY=($(compgen -W "$exec_commands" -- "$cur"))
                    ;;
                context-create)
                    # Context name (no completion needed)
                    ;;
                completion)
                    # Complete shell types
                    COMPREPLY=($(compgen -W "bash zsh fish" -- "$cur"))
                    ;;
            esac
            ;;
        3)
            case "${COMP_WORDS[1]}" in
                run|plumbing-exec)
                    # Continue completing commands/arguments
                    local exec_commands="bash sh python3 python ls cat cd pwd"
                    COMPREPLY=($(compgen -W "$exec_commands" -- "$cur"))
                    ;;
            esac
            ;;
    esac

    # Handle flags
    case "$prev" in
        --name|--context)
            # Complete context names
            local contexts=$(_dev_env_list_contexts)
            COMPREPLY=($(compgen -W "$contexts" -- "$cur"))
            ;;
        --path)
            # Complete directories
            COMPREPLY=($(compgen -d -- "$cur"))
            ;;
        --state-dir)
            # Complete directories
            COMPREPLY=($(compgen -d -- "$cur"))
            ;;
        -o|--output)
            # Complete files for completion output
            COMPREPLY=($(compgen -f -- "$cur"))
            ;;
    esac
}

_dev_env_list_contexts() {
    # List existing contexts using Python module
    python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    with state:
        rows = state.conn.execute('SELECT name FROM contexts ORDER BY last_used DESC').fetchall()
        print(' '.join(row[0] for row in rows))
except:
    pass
" 2>/dev/null
}

complete -F _dev_env_completion dev-env
complete -F _dev_env_completion 'python3 -m dev_env'
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
                work)
                    _arguments \
                        '--name[Context name]:name:_dev_env_contexts'
                    ;;
                stop)
                    _arguments \
                        '--name[Context name]:name:_dev_env_contexts'
                    ;;
                run)
                    _arguments \
                        '*:command:_command_names'
                    ;;
                status)
                    _arguments \
                        '--all[Show all environments]'
                    ;;
                shell)
                    # No additional arguments
                    ;;
                context-create)
                    _arguments \
                        '1:context name:' \
                        '--path[Path to context]:path:_directories'
                    ;;
                context-resolve)
                    _arguments \
                        '--name[Context name to resolve]:name:_dev_env_contexts'
                    ;;
                context-list)
                    # No additional arguments
                    ;;
                env-create|env-start|env-stop|env-status)
                    _arguments \
                        '--context[Context name]:context:_dev_env_contexts'
                    ;;
                plumbing-exec)
                    _arguments \
                        '--context[Context name]:context:_dev_env_contexts' \
                        '*:command:_command_names'
                    ;;
                plumbing-attach)
                    _arguments \
                        '--context[Context name]:context:_dev_env_contexts'
                    ;;
                completion)
                    _arguments \
                        '1:shell:(bash zsh fish)' \
                        '(-o --output)'{-o,--output}'[Output file]:file:_files'
                    ;;
            esac
            ;;
    esac
}

_dev_env_commands() {
    local commands=(
        'work:Start or resume development session'
        'stop:Stop development environment'  
        'run:Execute command in current environment'
        'status:Show environment status'
        'shell:Open interactive shell'
        'context-create:Create a new context'
        'context-resolve:Resolve context from path or name'
        'context-list:List all contexts'
        'env-create:Create environment from config'
        'env-start:Start existing environment'
        'env-stop:Stop running environment'
        'env-status:Get environment status'
        'plumbing-exec:Execute command in environment'
        'plumbing-attach:Attach to environment TTY'
        'completion:Generate shell completion scripts'
    )
    _describe 'commands' commands
}

_dev_env_contexts() {
    local contexts
    contexts=(${(f)"$(python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    with state:
        rows = state.conn.execute('SELECT name FROM contexts ORDER BY last_used DESC').fetchall()
        for row in rows:
            print(row[0])
except:
    pass
" 2>/dev/null)"})
    _describe 'contexts' contexts
}

_dev_env "$@"
""".strip()


def generate_fish_completion() -> str:
  """Generate fish completion script"""
  return """
# dev-env fish completion script

# Helper function to list contexts
function __dev_env_list_contexts
    python3 -c "
try:
    from dev_env.state import StateManager
    from pathlib import Path
    state = StateManager(Path.home() / '.dev-env' / 'state')
    with state:
        rows = state.conn.execute('SELECT name FROM contexts ORDER BY last_used DESC').fetchall()
        for row in rows:
            print(row[0])
except:
    pass
" 2>/dev/null
end

# Main command completions
complete -c dev-env -f
complete -c dev-env -n "__fish_use_subcommand" -a "work" -d "Start or resume development session"
complete -c dev-env -n "__fish_use_subcommand" -a "stop" -d "Stop development environment"
complete -c dev-env -n "__fish_use_subcommand" -a "run" -d "Execute command in current environment"
complete -c dev-env -n "__fish_use_subcommand" -a "status" -d "Show environment status"
complete -c dev-env -n "__fish_use_subcommand" -a "shell" -d "Open interactive shell"
complete -c dev-env -n "__fish_use_subcommand" -a "context-create" -d "Create a new context"
complete -c dev-env -n "__fish_use_subcommand" -a "context-resolve" -d "Resolve context from path or name"
complete -c dev-env -n "__fish_use_subcommand" -a "context-list" -d "List all contexts"
complete -c dev-env -n "__fish_use_subcommand" -a "env-create" -d "Create environment from config"
complete -c dev-env -n "__fish_use_subcommand" -a "env-start" -d "Start existing environment"
complete -c dev-env -n "__fish_use_subcommand" -a "env-stop" -d "Stop running environment"
complete -c dev-env -n "__fish_use_subcommand" -a "env-status" -d "Get environment status"
complete -c dev-env -n "__fish_use_subcommand" -a "plumbing-exec" -d "Execute command in environment"
complete -c dev-env -n "__fish_use_subcommand" -a "plumbing-attach" -d "Attach to environment TTY"
complete -c dev-env -n "__fish_use_subcommand" -a "completion" -d "Generate shell completion scripts"

# Global options
complete -c dev-env -l version -d "Show version"
complete -c dev-env -l state-dir -d "Directory for storing environment state" -r

# work command
complete -c dev-env -n "__fish_seen_subcommand_from work" -l name -d "Context name" -f -a "(__dev_env_list_contexts)"

# stop command
complete -c dev-env -n "__fish_seen_subcommand_from stop" -l name -d "Context name" -f -a "(__dev_env_list_contexts)"

# run command
complete -c dev-env -n "__fish_seen_subcommand_from run" -a "bash sh python3 python ls cat cd pwd" -d "Command to execute"

# status command
complete -c dev-env -n "__fish_seen_subcommand_from status" -l all -d "Show all environments"

# context-create command
complete -c dev-env -n "__fish_seen_subcommand_from context-create" -l path -d "Path to context" -r

# context-resolve command
complete -c dev-env -n "__fish_seen_subcommand_from context-resolve" -l name -d "Context name to resolve" -f -a "(__dev_env_list_contexts)"

# env commands
complete -c dev-env -n "__fish_seen_subcommand_from env-create env-start env-stop env-status" -l context -d "Context name" -f -a "(__dev_env_list_contexts)"

# plumbing-exec command
complete -c dev-env -n "__fish_seen_subcommand_from plumbing-exec" -l context -d "Context name" -f -a "(__dev_env_list_contexts)"
complete -c dev-env -n "__fish_seen_subcommand_from plumbing-exec; and __fish_prev_arg_in --context" -a "bash sh python3 python ls cat cd pwd" -d "Command to execute"

# plumbing-attach command
complete -c dev-env -n "__fish_seen_subcommand_from plumbing-attach" -l context -d "Context name" -f -a "(__dev_env_list_contexts)"

# completion command
complete -c dev-env -n "__fish_seen_subcommand_from completion" -f -a "bash zsh fish" -d "Shell type"
complete -c dev-env -n "__fish_seen_subcommand_from completion" -s o -l output -d "Output file" -r

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
