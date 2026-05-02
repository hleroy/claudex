#!/usr/bin/env python3
"""
Claudex - Claude Code Provider Switcher

Usage:
    claudex [provider] [args...]
    claudex --list
    claudex status
"""

import os
import sys
import json
import configparser
import difflib
import shutil

DEBUG = os.environ.get("CLAUDE_SWITCH_DEBUG", "0") == "1"

# Colors
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"

# Paths — XDG-aware, overridable
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
CONFIG_DIR = os.environ.get("CLAUDE_CONFIG_DIR", os.path.join(XDG_CONFIG_HOME, "claudex"))
PROVIDERS_PATH = os.path.join(CONFIG_DIR, "providers.ini")
CREDENTIALS_PATH = os.path.join(CONFIG_DIR, "credentials")
SETTINGS_PATH = os.environ.get("CLAUDE_SETTINGS", os.path.join(os.path.expanduser("~"), ".claude", "settings.json"))

# Env var keys written to settings.json (uppercase — Claude Code env var names)
PROVIDER_ENV_KEYS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "API_TIMEOUT_MS",
    "NONESSENTIAL_TRAFFIC",
]


def dbg(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def die(msg):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _load_settings(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except PermissionError as e:
        die(f"Cannot read {path}: {e}")
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to parse {path}: {e}", file=sys.stderr)
        return {}


def _save_settings(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _apply_model_overrides(section):
    updates = {}
    for tier in ["opus", "sonnet", "haiku"]:
        model = resolve_model(section, tier)
        if model:
            updates[f"ANTHROPIC_DEFAULT_{tier.upper()}_MODEL"] = model
    return updates


def load_credentials(path):
    """Parse provider=key format. Returns dict of provider_name -> api_key."""
    creds = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    creds[key.strip()] = val.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return creds


def resolve_model(section, tier):
    key_map = {
        "opus": ["opus_model", "model"],
        "sonnet": ["sonnet_model", "model"],
        "haiku": ["haiku_model", "small_fast_model", "model"],
    }
    for key in key_map.get(tier, []):
        if key in section:
            return section.get(key)
    return None


def merge_settings(settings_path, env_updates):
    if not env_updates:
        return
    data = _load_settings(settings_path)
    data.setdefault("env", {})
    for key, value in env_updates.items():
        if value is None:
            pass
        elif value == "":
            data["env"].pop(key, None)
        else:
            data["env"][key] = value
    _save_settings(settings_path, data)


def clear_provider_settings(settings_path):
    try:
        with open(settings_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to parse {settings_path}: {e}", file=sys.stderr)
        return
    env = data.get("env", {})
    for key in PROVIDER_ENV_KEYS:
        env.pop(key, None)
    data["env"] = env
    _save_settings(settings_path, data)


def handle_ollama(section):
    env_updates = {}

    env_updates["ANTHROPIC_BASE_URL"] = section.get("host", fallback="http://localhost:11434")
    env_updates["ANTHROPIC_AUTH_TOKEN"] = "ollama"
    env_updates["ANTHROPIC_API_KEY"] = ""

    ollama_model = section.get("model", fallback=None)
    if ollama_model:
        env_updates["ANTHROPIC_DEFAULT_OPUS_MODEL"] = ollama_model
        env_updates["ANTHROPIC_DEFAULT_SONNET_MODEL"] = ollama_model
        env_updates["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = ollama_model

    env_updates["API_TIMEOUT_MS"] = section.get("timeout_ms", fallback="600000")
    env_updates["NONESSENTIAL_TRAFFIC"] = section.get("nonessential_traffic", fallback="1")

    return env_updates


def handle_standard_provider(section, provider_name, credentials):
    env_updates = {}

    api_key = credentials.get(provider_name) or section.get("api_key", fallback=None)
    base_url = section.get("base_url", fallback=None)

    if api_key:
        env_updates["ANTHROPIC_AUTH_TOKEN"] = api_key
        env_updates["ANTHROPIC_API_KEY"] = ""

    if base_url:
        env_updates["ANTHROPIC_BASE_URL"] = base_url

    env_updates.update(_apply_model_overrides(section))

    timeout = section.get("timeout_ms", fallback=None)
    if timeout:
        env_updates["API_TIMEOUT_MS"] = timeout

    env_updates["NONESSENTIAL_TRAFFIC"] = section.get("nonessential_traffic", fallback="")

    return env_updates


def find_claude():
    return shutil.which("claude")


def switch_and_launch(provider_name, extra_args):
    if not os.path.exists(PROVIDERS_PATH):
        die(f"Config file not found: {PROVIDERS_PATH}\nRun install.sh first.")

    real_claude = find_claude()
    if not real_claude:
        die("Claude Code CLI not found in PATH.\n"
            "Install it: curl -fsSL https://claude.ai/install.sh | bash")

    config = configparser.ConfigParser()
    config.read(PROVIDERS_PATH)

    if not provider_name:
        provider_name = "anthropic"

    # anthropic is the hardcoded default — always available
    if provider_name.lower() == "anthropic":
        clear_provider_settings(SETTINGS_PATH)
        if config.has_section("anthropic"):
            model_updates = _apply_model_overrides(config["anthropic"])
            if model_updates:
                merge_settings(SETTINGS_PATH, model_updates)

    elif not config.has_section(provider_name):
        sections = config.sections()
        suggestions = difflib.get_close_matches(provider_name, sections, n=1, cutoff=0.6)
        hint = f"\nDid you mean: {suggestions[0]}?" if suggestions else ""
        die(f"Provider [{provider_name}] not found in config.{hint}")

    elif provider_name.lower() == "ollama":
        merge_settings(SETTINGS_PATH, handle_ollama(config[provider_name]))

    else:
        section = config[provider_name]
        credentials = load_credentials(CREDENTIALS_PATH)
        env_updates = handle_standard_provider(section, provider_name, credentials)
        required = ["ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"]
        missing = [k for k in required if k not in env_updates or not env_updates[k]]
        if missing:
            die(
                f"Provider [{provider_name}] has incomplete config (missing: {', '.join(missing)}).\n"
                f"Check that {PROVIDERS_PATH} has a base_url and that "
                f"{CREDENTIALS_PATH} has a key for [{provider_name}]."
            )
        merge_settings(SETTINGS_PATH, env_updates)

    print(f">>> Using provider: {provider_name}", file=sys.stderr)

    os.execv(real_claude, [real_claude] + extra_args)


def _detect_active_provider(config):
    """Return (provider_name, section) detected from settings.json, or (None, None)."""
    settings = _load_settings(SETTINGS_PATH)
    env = settings.get("env", {})

    base_url = env.get("ANTHROPIC_BASE_URL", "")
    auth_token = env.get("ANTHROPIC_AUTH_TOKEN", "")

    if not base_url and not auth_token:
        return "anthropic", None

    if auth_token == "ollama":
        section = config["ollama"] if config.has_section("ollama") else None
        return "ollama", section

    for section_name in config.sections():
        if section_name == "anthropic":
            continue
        section_base = config[section_name].get("base_url", "")
        if section_base and section_base == base_url:
            return section_name, config[section_name]

    return None, None


def _fmt_line(label, value, value_color=""):
    """Format an indented line with a right-padded label."""
    end = NC if value_color else ""
    return f"  {label:<12} {value_color}{value}{end}"


def cmd_status():
    config = configparser.ConfigParser()
    if os.path.exists(PROVIDERS_PATH):
        config.read(PROVIDERS_PATH)

    settings = _load_settings(SETTINGS_PATH)
    env = settings.get("env", {})

    active_name, active_section = _detect_active_provider(config)

    # --- Active provider ---
    label = active_name or "unknown"
    color = GREEN if active_name else RED
    print(f"{BOLD}Active provider:{NC} {color}{label}{NC}")

    if active_section:
        if active_name == "ollama":
            base_url = active_section.get("host") or env.get("ANTHROPIC_BASE_URL", "")
        else:
            base_url = active_section.get("base_url") or env.get("ANTHROPIC_BASE_URL", "")
        if base_url:
            print(_fmt_line("Base URL:", base_url, CYAN))
        for tier in ("opus", "sonnet", "haiku"):
            model = env.get(f"ANTHROPIC_DEFAULT_{tier.upper()}_MODEL", "")
            if model:
                print(_fmt_line(tier.capitalize() + ":", model))
        timeout = env.get("API_TIMEOUT_MS", "")
        if timeout:
            print(_fmt_line("Timeout:", timeout + "ms"))
    elif active_name == "anthropic":
        for tier in ("opus", "sonnet", "haiku"):
            model = env.get(f"ANTHROPIC_DEFAULT_{tier.upper()}_MODEL", "")
            if model:
                print(_fmt_line(tier.capitalize() + ":", model))
    elif active_name is None:
        base_url = env.get("ANTHROPIC_BASE_URL", "")
        if base_url:
            print(_fmt_line("Base URL:", base_url, CYAN))
        for tier in ("opus", "sonnet", "haiku"):
            model = env.get(f"ANTHROPIC_DEFAULT_{tier.upper()}_MODEL", "")
            if model:
                print(_fmt_line(tier.capitalize() + ":", model))

    # --- Available providers ---
    providers = ["anthropic"] + [s for s in config.sections() if s != "anthropic"]
    if providers:
        parts = []
        for p in providers:
            if p == active_name:
                parts.append(f"{GREEN}{p} ●{NC}")
            else:
                parts.append(p)
        print(f"\n{BOLD}Available:{NC} {', '.join(parts)}")

    # --- Config location (one line, de-emphasized) ---
    if os.path.isdir(CONFIG_DIR):
        home = os.path.expanduser("~")
        if CONFIG_DIR.startswith(home):
            display = "~" + CONFIG_DIR[len(home):]
        else:
            display = CONFIG_DIR
        print(f"{BOLD}Config:{NC} {display}/")


def cmd_list():
    print("Available Claude providers:")
    print("  - anthropic (default)")

    if os.path.exists(PROVIDERS_PATH):
        config = configparser.ConfigParser()
        config.read(PROVIDERS_PATH)
        for section in config.sections():
            if section == "anthropic":
                continue
            print(f"  - {section}")


def main():
    args = sys.argv[1:]

    if not args:
        real_claude = find_claude()
        if not real_claude:
            die("Claude Code CLI not found in PATH.")
        os.execv(real_claude, [real_claude])
        return

    first = args[0]

    if first in ("-h", "--help"):
        print(f"""Usage:
  claudex [provider] [args...]
  claudex --list
  claudex status

Commands:
  <provider>   Switch to provider and launch Claude Code
  (no args)    Launch Claude Code with current settings
  --list       List available providers from {PROVIDERS_PATH}
  status       Show current configuration paths and active provider
  -h, --help   Show this help message

Config files:
  {PROVIDERS_PATH}
  {CREDENTIALS_PATH}
""")
        return

    if first == "--list":
        cmd_list()
        return

    if first == "status":
        cmd_status()
        return

    switch_and_launch(first, args[1:])


if __name__ == "__main__":
    main()
