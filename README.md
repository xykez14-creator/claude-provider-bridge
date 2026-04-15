# Claude Provider Bridge

A lightweight bridge that allows Claude Code to work with Ollama Cloud and OpenRouter providers by translating API responses to Anthropic format.

**Works on Linux, macOS, and Windows.**

## Why This?

Claude Code doesn't natively support third-party AI providers. This project creates local proxies that:
1. Forward requests to Ollama Cloud or OpenRouter
2. Convert responses to exact Anthropic format that Claude Code expects

## Quick Start

### 1. Install Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv

# Activate it
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate            # Windows (cmd)
venv\Scripts\Activate.ps1        # Windows (PowerShell)

# Install packages
pip install -r requirements.txt
```

### 2. Configure

```bash
# Create your config from the template
cp .env.example .env             # Linux / macOS
copy .env.example .env           # Windows

# Set your API keys
python bridge.py set ollama-key YOUR_OLLAMA_KEY
python bridge.py set openrouter-key sk-or-v1-YOUR_KEY

# View current config
python bridge.py config
```

### 3. Start Proxies

```bash
python bridge.py start
```

### 4. Connect Claude Code

```bash
# Switch to Ollama
python bridge.py switch ollama

# Or switch to OpenRouter
python bridge.py switch openrouter

# Then run Claude Code
claude
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `python bridge.py config` | Show current configuration |
| `python bridge.py set <key> <value>` | Update a config value |
| `python bridge.py start` | Start all proxy servers |
| `python bridge.py switch <provider>` | Configure Claude Code for a provider |

### Configurable Keys

| Key | Default | Description |
|-----|---------|-------------|
| `ollama-key` | — | Ollama Cloud API key |
| `ollama-url` | `https://ollama.com/api/chat` | Ollama API endpoint |
| `ollama-port` | `4000` | Local proxy port for Ollama |
| `ollama-model` | `glm-5.1` | Default Ollama model |
| `openrouter-key` | — | OpenRouter API key |
| `openrouter-url` | `https://openrouter.ai/api/v1/chat/completions` | OpenRouter API endpoint |
| `openrouter-port` | `4001` | Local proxy port for OpenRouter |
| `openrouter-model` | `nvidia/nemotron-3-super-120b-a12b:free` | Default OpenRouter model |

### Examples

```bash
# Change the Ollama port to 5000
python bridge.py set ollama-port 5000

# Use a different OpenRouter model
python bridge.py set openrouter-model qwen/qwen3.6-plus:free

# Change the Ollama default model
python bridge.py set ollama-model qwen3.5:397b
```

## API Keys

### OpenRouter
Get your key from [openrouter.ai/keys](https://openrouter.ai/keys):
```bash
python bridge.py set openrouter-key sk-or-v1-YOUR-KEY
```

### Ollama Cloud
Get your key from [ollama.com/cloud](https://ollama.com/cloud):
```bash
python bridge.py set ollama-key YOUR-KEY
```

> **Note:** Keys are stored in `.env` (git-ignored). Never commit your keys. Use `.env.example` as a template.

## Troubleshooting

### "externally-managed-environment" error (Arch Linux)
Use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### "q.map is not a function" error
This happens when the response format is wrong. Make sure the proxy is converting to Anthropic format:
```json
{
  "content": [{"type": "text", "text": "..."}]
}
```

### Connection refused
Ensure proxy is running:
```bash
curl http://localhost:4000/health
curl http://localhost:4001/health
```

## License

MIT. Feel free to fork, customize, and share.

## Contributing

Issues and PRs welcome at https://github.com/xykez14-creator/claude-provider-bridge.git

## Donations (Seriously)

I built this bridge because I believe in empowering Claude Provider Bridge users with best-practice configurations. It's free and will always be free.

**Why donate?** I'm currently fully broke (hahaha) and maintaining/supporting this takes time and mental energy. If this tool saved you hours or made your setup rock-solid, consider tossing a few satoshis, gwei, or lamports my way.

**Crypto addresses (all blockchain native, no wrap/token required):**

- **BTC (Bitcoin):** `182WQikKNMM9qRKtDVAmrPaoC5C3zv76Rk`
- **ETH (ERC-20):** `0xd40af35b5a29bb04dbd25c00e9a006e985b41090`
- **SOL (Solana):** `12eTSDNs4NWJrv77ZZJ2g5S8gEK2NQzhFXrWCnwAhYC3`

**Want a thank you note?** Email me at [xykez77@proton.com](mailto:xykez77@proton.com) after sending — I'd love to express my gratitude personally.

No strings attached — donations don't affect development, but they keep the lights on (literally). Thank you! 🙏
