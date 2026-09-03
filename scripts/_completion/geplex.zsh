#compdef geplex geplex-backup geplex-calendar geplex-contacts geplex-cookbook geplex-docs geplex-gallery geplex-mail geplex-mcp geplex-memory geplex-notes geplex-personal geplex-preset geplex-research geplex-sessions geplex-signature geplex-skills geplex-tasks geplex-theme geplex-webhook
# Zsh tab-completion for the geplex umbrella + sub-CLIs.
#
# Drop in any directory on $fpath, e.g.:
#     fpath=(/path/to/geplex-ui/scripts/_completion $fpath)
#     autoload -U compinit; compinit
#
# Then `geplex <tab>` completes subcommands; `geplex mail <tab>`
# completes mail subcommands; `geplex-mail <tab>` works the same.

_geplex_scripts_dir() {
    local self="${(%):-%x}"
    while [[ -L "$self" ]]; do self="$(readlink "$self")"; done
    cd "${self:h}/.." && pwd
}

typeset -gA _geplex_subs

_geplex_refresh() {
    _geplex_subs=()
    local dir="$(_geplex_scripts_dir)"
    local py="$dir/../venv/bin/python"
    [[ -x "$py" ]] || py="$(command -v python3)"
    local f sub help_out commands
    for f in "$dir"/geplex-*; do
        [[ -x "$f" ]] || continue
        case "$f" in
            *.bak|*.pyc|*.pre-*) continue ;;
        esac
        sub="${${f:t}#geplex-}"
        help_out=$("$py" "$f" --help 2>/dev/null) || continue
        commands=$(echo "$help_out" | grep -oE '\{[a-z0-9_,-]+\}' | head -1 \
            | tr -d '{}' | tr ',' ' ')
        _geplex_subs[$sub]="$commands"
    done
}

_geplex() {
    [[ ${#_geplex_subs} -eq 0 ]] && _geplex_refresh

    local cmd="${words[1]}"

    if [[ "$cmd" == "geplex" ]]; then
        if (( CURRENT == 2 )); then
            local -a subs=(${(k)_geplex_subs} help)
            _describe 'subcommand' subs
            return
        fi
        local sub="${words[2]}"
        if [[ "$sub" == "help" ]] && (( CURRENT == 3 )); then
            local -a subs=(${(k)_geplex_subs})
            _describe 'subcommand' subs
            return
        fi
        if (( CURRENT == 3 )); then
            local -a sc=(${(s/ /)_geplex_subs[$sub]})
            _describe 'command' sc
            return
        fi
        return
    fi

    # geplex-foo <tab>
    local sub="${cmd#geplex-}"
    if (( CURRENT == 2 )); then
        local -a sc=(${(s/ /)_geplex_subs[$sub]})
        _describe 'command' sc
        return
    fi
}

_geplex "$@"
