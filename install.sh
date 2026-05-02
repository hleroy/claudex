#!/usr/bin/env bash
set -euo pipefail

# Claudex installer
# Usage:
#   ./install.sh            Install claudex
#   ./install.sh --update   Re-symlink claudex to current source
#   ./install.sh --uninstall  Remove symlink; --purge also removes config

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || SCRIPT_DIR="$(pwd)"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/claudex"
LOCAL_BIN="$HOME/.local/bin"
CLAUDEX_SRC="$SCRIPT_DIR/claudex.py"
PROVIDERS_EXAMPLE="$SCRIPT_DIR/providers.ini.example"
CREDENTIALS_EXAMPLE="$SCRIPT_DIR/credentials.example"

REPO_BASE="https://raw.githubusercontent.com/hleroy/claudex/main"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

msg()  { echo -e "${GREEN}${*}${NC}"; }
warn() { echo -e "${YELLOW}${*}${NC}" >&2; }
err()  { echo -e "${RED}${*}${NC}" >&2; }

_tilde() {
    # Replace $HOME prefix with ~ for readability
    local p="${1}"
    if [[ "$p" == "$HOME"/* ]]; then
        echo "~${p#$HOME}"
    else
        echo "$p"
    fi
}

_is_piped() {
    # Piped mode: running via curl|bash, not from a cloned repo
    [[ ! -f "$CLAUDEX_SRC" ]]
}

_download() {
    local url="${REPO_BASE}/${1}"
    local dest="${2}"
    curl -fsSL "$url" -o "$dest" || {
        err "Failed to download ${url}"
        exit 1
    }
}

copy_if_missing() {
    local dest="$1" src="$2"
    if [[ -f "$dest" ]]; then
        return 1
    elif [[ -f "$src" ]]; then
        cp "$src" "$dest"
        return 0
    else
        return 1
    fi
}

install() {
    mkdir -p "$CONFIG_DIR" "$LOCAL_BIN"

    if _is_piped; then
        CLAUDEX_SRC="$CONFIG_DIR/claudex.py"
        _download "claudex.py" "$CLAUDEX_SRC"
        chmod +x "$CLAUDEX_SRC"

        local tmpdir
        tmpdir=$(mktemp -d)
        _download "providers.ini.example" "$tmpdir/providers.ini.example"
        _download "credentials.example" "$tmpdir/credentials.example"
        PROVIDERS_EXAMPLE="$tmpdir/providers.ini.example"
        CREDENTIALS_EXAMPLE="$tmpdir/credentials.example"
    elif [[ ! -f "$CLAUDEX_SRC" ]]; then
        err "claudex.py not found at $CLAUDEX_SRC"
        err "Run this script from the Claudex source directory."
        exit 1
    fi

    local config_written=false creds_written=false

    if copy_if_missing "$CONFIG_DIR/providers.ini" "$PROVIDERS_EXAMPLE"; then
        config_written=true
    fi

    if copy_if_missing "$CONFIG_DIR/credentials" "$CREDENTIALS_EXAMPLE"; then
        chmod 600 "$CONFIG_DIR/credentials"
        creds_written=true
    fi

    # Status line for config files
    local config_status=""
    if $config_written && $creds_written; then
        config_status="written"
    elif ! $config_written && ! $creds_written; then
        config_status="skipped, already exists"
    else
        config_status="written (partial)"
    fi

    ln -sf "$CLAUDEX_SRC" "$LOCAL_BIN/claudex"

    msg "Config:  $(_tilde "$CONFIG_DIR")/ ($config_status)"
    if $creds_written; then
        warn "         credentials — add your API keys"
    fi
    msg "Binary:  $(_tilde "$LOCAL_BIN")/claudex -> $(_tilde "$CLAUDEX_SRC")"
    echo ""
    msg "Installed."
    echo ""
    msg "Next steps:"
    msg "  1. Add your API keys:  nano $(_tilde "$CONFIG_DIR")/credentials"
    msg "  2. Review providers:   nano $(_tilde "$CONFIG_DIR")/providers.ini"
    msg "  3. Switch and launch:  claudex <provider>"
}

update() {
    if _is_piped; then
        CLAUDEX_SRC="$CONFIG_DIR/claudex.py"
        _download "claudex.py" "$CLAUDEX_SRC"
        chmod +x "$CLAUDEX_SRC"
    elif [[ ! -f "$CLAUDEX_SRC" ]]; then
        err "claudex.py not found at $CLAUDEX_SRC"
        exit 1
    fi
    mkdir -p "$LOCAL_BIN"
    ln -sf "$CLAUDEX_SRC" "$LOCAL_BIN/claudex"
    msg "Updated: $(_tilde "$LOCAL_BIN")/claudex -> $(_tilde "$CLAUDEX_SRC")"
}

uninstall() {
    local purge=false
    [[ "${1:-}" == "--purge" ]] && purge=true

    if [[ -L "$LOCAL_BIN/claudex" ]]; then
        rm "$LOCAL_BIN/claudex"
        msg "Removed: $(_tilde "$LOCAL_BIN")/claudex"
    elif [[ -f "$LOCAL_BIN/claudex" ]]; then
        warn "$(_tilde "$LOCAL_BIN")/claudex exists but is not a symlink — skipped"
    else
        warn "No claudex symlink found at $(_tilde "$LOCAL_BIN")/"
    fi

    if $purge; then
        if [[ -f "$CONFIG_DIR/providers.ini" ]]; then
            read -rp "Remove $(_tilde "$CONFIG_DIR")/providers.ini? [y/N]: " ans
            if [[ "$ans" =~ ^[Yy](es)?$ ]]; then
                rm "$CONFIG_DIR/providers.ini"
                msg "  Removed."
            fi
        fi
        if [[ -f "$CONFIG_DIR/credentials" ]]; then
            read -rp "Remove $(_tilde "$CONFIG_DIR")/credentials? [y/N]: " ans
            if [[ "$ans" =~ ^[Yy](es)?$ ]]; then
                rm "$CONFIG_DIR/credentials"
                msg "  Removed."
            fi
        fi
    fi

}

# --- main ---
case "${1:-install}" in
    -h|--help)
        echo "Usage: ./install.sh [install|--update|--uninstall [--purge]]"
        ;;
    install)
        install
        ;;
    --update|update)
        update
        ;;
    --uninstall|uninstall)
        uninstall "${2:-}"
        ;;
    *)
        err "Unknown command: $1"
        exit 1
        ;;
esac
