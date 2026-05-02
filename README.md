# Claudex

**Claudex** 🔄 — Claude Code Provider Switcher

### 💸 Your Pro plan runs out too fast. Don't buy Extra Usage — switch providers instead.

If you're on Claude Pro ($20/month) and hitting the usage wall mid-session, the built-in fix is "Extra Usage" — Anthropic's pay-as-you-go credits at Opus API prices ($25/M output tokens). That gets expensive quickly.

**Claudex gives you a cheaper off-ramp.** Instead of topping up at Anthropic's rates, point Claude Code at a different provider and keep coding. Your Pro plan stays active for lighter work; Claudex kicks in when you need a long session without watching the meter.

**DeepSeek V4** (April 2026) is the standout. On SWE-bench Verified — the standard benchmark for real-world bug fixes — V4-Pro scores 80.6% to Opus 4.6's 80.8%. On LiveCodeBench, it pulls ahead 93.5% to 88.8%. Yet its API pricing is roughly **7× lower** than Opus 4.7 ($3.48 vs $25 per million output tokens).

🚀 One command, same Claude Code experience:

```bash
claudex deepseek    # switch to DeepSeek V4 and launch
claudex ollama      # go fully local, zero cost
claudex             # launch with current provider
```

## ✨ Features

- ⚡ **Single command** — `claudex <provider>` switches and launches Claude Code in one step
- 🧩 **Native config** — writes to Claude Code's own settings file, no wrapper scripts
- 🦙 **Ollama support** — full local LLM inference with automatic dummy auth token
- 🔐 **Credentials separation** — API keys in a separate `chmod 600` file, never in INI config
- 📂 **Config under `~/.config/claudex/`** — follows standard Linux conventions (`XDG_CONFIG_HOME`)
- 🔁 **Persistent switching** — provider stays active across terminal sessions until switched again

## 📦 Install

### ⬇️ Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/hleroy/claudex/refs/heads/main/install.sh | bash
```

### 🐙 Clone & Install

```bash
git clone https://github.com/hleroy/claudex.git
cd claudex
./install.sh
```

## ⚙️ Setup

```bash
# 1. Add your API keys
nano ~/.config/claudex/credentials

# 2. Edit providers (optional)
nano ~/.config/claudex/providers.ini

# 3. Switch and launch
claudex deepseek
claudex ollama
claudex                # use default provider
```

## 🛠️ Configuration

All config lives under `~/.config/claudex/` (or `$CLAUDE_CONFIG_DIR`).

### `providers.ini`

```ini
[deepseek]
base_url=https://api.deepseek.com/anthropic
opus_model=deepseek-v4-pro
sonnet_model=deepseek-v4-pro
haiku_model=deepseek-v4-flash

[ollama]
host=http://localhost:11434
model=qwen2.5-coder:32b
timeout_ms=600000
nonessential_traffic=1
```

Keys: `base_url`, `opus_model`, `sonnet_model`, `haiku_model`, `model` (fallback for all tiers), `timeout_ms`, `nonessential_traffic`.

### `credentials`

One `provider=key` per line. The provider name (before `=`) must match a section in `providers.ini`.

```
deepseek=sk-...
minimax=eyJ...
glm=...
```

Keep this file `chmod 600`.

### 🌍 Environment variable overrides

| Variable                  | Purpose                           | Default                        |
|---------------------------|-----------------------------------|--------------------------------|
| `CLAUDE_CONFIG_DIR`       | Override config directory         | `$XDG_CONFIG_HOME/claudex`     |
| `CLAUDE_SETTINGS`         | Override settings.json path       | `~/.claude/settings.json`      |
| `CLAUDE_SWITCH_DEBUG=1`   | Verbose stderr debug output       | off                            |

## ⌨️ Commands

| Command              | Behavior                                                     |
|----------------------|--------------------------------------------------------------|
| `claudex <provider>` | Switch to provider and launch Claude Code                    |
| `claudex`            | Launch Claude Code with current settings (no switch)         |
| `claudex --list`     | List available providers                                     |
| `claudex status`     | Show config paths and active provider                        |
| `claudex -h`         | Show help                                                    |

Arguments after the provider name are forwarded to Claude Code:

```bash
claudex deepseek -p "Explain this code"
claudex ollama --resume
```

## 🌐 Supported Providers

| Provider   | Base URL                                   | Key Name                   |
|------------|--------------------------------------------|----------------------------|
| anthropic  | (native, no base_url needed)               | `anthropic`                |
| deepseek   | `https://api.deepseek.com/anthropic`       | `deepseek`                 |
| minimax    | `https://api.minimax.io/anthropic`         | `minimax`                  |
| glm        | `https://api.z.ai/api/anthropic`           | `glm`                      |
| kimi       | `https://api.moonshot.ai/anthropic`        | `kimi`                     |
| mistral    | `https://api.mistral.ai/api/anthropic`     | `mistral`                  |
| ollama     | `http://localhost:11434`                   | (none — local, no API key) |

### ➕ Adding a new provider

1. Add a section to `~/.config/claudex/providers.ini`:

```ini
[myprovider]
base_url=https://api.myprovider.com/anthropic
opus_model=my-model
sonnet_model=my-model
haiku_model=my-model-fast
```

2. Add your key to `~/.config/claudex/credentials`:

```
myprovider=your-api-key
```

3. Switch immediately:

```bash
claudex myprovider
```

## 🦙 Ollama

```ini
[ollama]
host=http://localhost:11434
model=qwen2.5-coder:32b
timeout_ms=600000
nonessential_traffic=1
```

Claudex automatically sets `ANTHROPIC_BASE_URL` to `host`, uses `ollama` as the auth token, clears `ANTHROPIC_API_KEY`, maps all model tiers to `model`, increases timeout, and disables telemetry.

## 🏗️ Installer flags

```bash
./install.sh --update               # Re-symlink claudex to current source
./install.sh --uninstall            # Remove symlink
./install.sh --uninstall --purge    # Also remove config files
```

## 🔍 Troubleshooting

### claudex command not found
Run `hash -r` or open a new terminal. Ensure `~/.local/bin` is in PATH.

### Provider has incomplete config
Check that the provider section in `providers.ini` has a `base_url` and that `credentials` contains a matching key.

### Wrong provider active
Run `claudex status` to see the active `BASE_URL`. Re-run `claudex <provider>` to switch.

## 📄 License

MIT License — see LICENSE file.
