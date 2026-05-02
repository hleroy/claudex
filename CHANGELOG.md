# Changelog

All notable changes to Claudex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Test suite: 118 unit tests covering credentials, model resolution, settings I/O, provider handlers, output commands, integration paths, and `install.sh` shell smoke tests.

### Fixed

- Atomic writes to settings.json (write to temp file then `os.replace`) to prevent torn writes.
- `switch_and_launch` now verifies the `claude` binary before modifying settings, avoiding partial state on missing install.
- `PermissionError` on `settings.json` now exits with a clear error instead of silently returning empty config.
- Removed unreachable `ANTHROPIC_API_KEY` code path in `handle_standard_provider`.
- `cmd_status` now reads Ollama's `host` key directly instead of relying on env-var fallback.

### Changed

- Anthropic is now a hardcoded built-in default — no longer requires a `[DEFAULT]` or `[anthropic]` section in `providers.ini`.
- Simplified `claudex status` output: drops file path clutter, shows active provider and model assignments prominently, marks active in available list, uses `~` for paths.
- Simplified `install.sh` user output: removed step numbering, consolidated config status into summary lines, replaced full paths with `~` shorthand, added numbered next-steps guide at end.

## [0.1.0] — 2026-05-02

### Added

- Initial release: `claudex` CLI for switching Claude Code between LLM providers.
- Support for Anthropic, DeepSeek, Ollama, MiniMax, GLM, Kimi, and Mistral providers.
- `claudex --list` to list available providers.
- `claudex status` to show config paths and active provider.
- `install.sh` for one-time setup (symlink + config files).

[Unreleased]: https://github.com/herveleroy/claudex/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/herveleroy/claudex/releases/tag/v0.1.0
