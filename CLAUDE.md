# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claudex is a Python 3 CLI tool (zero external dependencies beyond stdlib) that switches Claude Code between different LLM providers (Anthropic, Ollama, MiniMax, Kimi, GLM, Mistral, DeepSeek). It writes provider env vars directly to `~/.claude/settings.json`, which Claude Code reads natively — no binary shadowing.

## Commands

```bash
# User-facing
claudex <provider>      # Switch provider and launch Claude Code
claudex                 # Launch Claude Code with current settings
claudex --list          # List available providers
claudex status          # Show config paths and active provider

# Development / setup
./install.sh            # Install claudex symlink + config files
./install.sh --update   # Re-symlink from current source
./install.sh --uninstall [--purge]  # Remove symlink; --purge also removes config
```

No build step or lint configuration exists — this is a stdlib-only repository. However, `ruff` is available: always run `ruff check <file>` on any generated or modified Python code before committing.

## Tests

```bash
PYTHONPATH=. python -m unittest discover tests/ -v   # run all tests (~117)
```

Tests use only `unittest` and `unittest.mock` (stdlib), zero external test dependencies. Temporary filesystem state uses `tempfile.TemporaryDirectory` — no disk pollution. `os.execv` and `shutil.which` are mocked in integration tests since they require a real Claude Code installation.

**`tests/test_claudex.py`** — 117 tests across 16 classes covering:
- `load_credentials`, `resolve_model`, `_apply_model_overrides`, `_fmt_line` (pure functions)
- `_load_settings`, `_save_settings`, `merge_settings`, `clear_provider_settings` (JSON I/O)
- `handle_ollama`, `handle_standard_provider`, `_detect_active_provider` (provider handlers)
- `cmd_list`, `cmd_status` (output commands)
- `switch_and_launch`, `main` (integration, with mocked `os.execv` and `shutil.which`)
- `install.sh` shell smoke tests via `subprocess` (bash functions: `_tilde`, `copy_if_missing`, `update`)

**What is NOT tested**: `os.execv` (process-replacing), real `claude` binary, real network calls, `install.sh` interactive prompts, `chmod 600`.

## Before Committing

Always update `CHANGELOG.md` before committing changes. Add entries under the `[Unreleased]` section following Keep a Changelog format. When releasing, move `[Unreleased]` entries to a new version section and bump the version following Semantic Versioning.

Use [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages: `type(scope): description`. Common types: `feat`, `fix`, `docs`, `refactor`, `chore`.

## Architecture

Two files:

**`claudex.py`** — The tool itself. `main()` dispatches to:
- `switch_and_launch()` — loads credentials, reads providers.ini, writes env vars to settings.json, then `os.execv()`s the real `claude` binary.
- `cmd_status()` — prints config paths, available providers, active BASE_URL.
- `cmd_list()` — lists provider sections from providers.ini.

Provider handling:
- `anthropic` — clears all provider env vars (restores Claude Code defaults), then optionally applies custom models.
- `ollama` — `handle_ollama()` sets `ANTHROPIC_AUTH_TOKEN=ollama` (dummy), clears `ANTHROPIC_API_KEY`, maps all model tiers to `model`.
- Everything else — `handle_standard_provider()` sets `ANTHROPIC_AUTH_TOKEN` + `ANTHROPIC_BASE_URL` for third-party APIs, or `ANTHROPIC_API_KEY` for native Anthropic.

**`install.sh`** — One-time setup. Creates `~/.config/claudex/`, copies example files, symlinks `claudex.py` → `~/.local/bin/claudex`, ensures `~/.local/bin` in `~/.bashrc` PATH.

## Config Files

| File                                   | Purpose                                                          |
|----------------------------------------|------------------------------------------------------------------|
| `~/.config/claudex/providers.ini`      | Provider definitions (INI, `chmod 644`)                          |
| `~/.config/claudex/credentials`        | API keys as `provider=key` lines (`chmod 600`)                   |
| `~/.claude/settings.json`              | Claude Code settings; `env` block is written by claudex          |

Override with `CLAUDE_CONFIG_DIR` (config dir) and `CLAUDE_SETTINGS` (settings.json path). Set `CLAUDE_SWITCH_DEBUG=1` for verbose debug output to stderr.

## Design Decisions

- **No PATH shadowing** — `claudex` and `claude` are separate commands. The user runs `claudex <provider>` to switch+launch, then `claude` works directly.
- **Credentials by section name** — the provider section name in INI is the lookup key in the credentials file. No `API_KEY_VAR` indirection. Simple `provider=key` format.
- **XDG-aware** — config under `~/.config/claudex/`, respects `XDG_CONFIG_HOME`.
- **INI keys are lowercase** — `base_url`, `opus_model`, etc. ConfigParser lowercases keys anyway.
