#!/usr/bin/env python3
"""Claude Provider Bridge CLI — manage config and run proxies."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"

# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------

def load_env() -> dict:
    """Parse .env into a dict (preserves comments as metadata)."""
    values = {}
    if not ENV_FILE.exists():
        return values
    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, _, val = stripped.partition("=")
            values[key.strip()] = val.strip()
    return values


def save_env(values: dict) -> None:
    """Write values back to .env, preserving comment structure."""
    lines = []
    if ENV_FILE.exists():
        existing_lines = ENV_FILE.read_text().splitlines()
    else:
        existing_lines = []

    written_keys = set()
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in values:
                lines.append(f"{key}={values[key]}")
                written_keys.add(key)
            else:
                lines.append(line)
        else:
            lines.append(line)

    # Append any new keys not in the original file
    for key, val in values.items():
        if key not in written_keys:
            lines.append(f"{key}={val}")

    ENV_FILE.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Key name mapping:  CLI-friendly -> .env key
# ---------------------------------------------------------------------------

KEY_MAP = {
    "ollama-key":       "OLLAMA_KEY",
    "ollama-url":       "OLLAMA_URL",
    "ollama-port":      "OLLAMA_PORT",
    "ollama-model":     "OLLAMA_MODEL",
    "openrouter-key":   "OPENROUTER_KEY",
    "openrouter-url":   "OPENROUTER_URL",
    "openrouter-port":  "OPENROUTER_PORT",
    "openrouter-model": "OPENROUTER_MODEL",
}

SENSITIVE_KEYS = {"OLLAMA_KEY", "OPENROUTER_KEY"}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_config(_args) -> None:
    """Show current configuration."""
    env = load_env()
    if not env:
        print("No .env file found. Run:  cp .env.example .env")
        sys.exit(1)

    print("Claude Provider Bridge — Current Config")
    print("=" * 42)
    for cli_name, env_key in KEY_MAP.items():
        val = env.get(env_key, "(not set)")
        if env_key in SENSITIVE_KEYS and val != "(not set)":
            val = val[:8] + "..." + val[-4:]
        print(f"  {cli_name:20s} {val}")
    print()


def cmd_set(args) -> None:
    """Update a config value."""
    name = args.name.lower()
    value = args.value

    if name not in KEY_MAP:
        print(f"Unknown config key: {name}")
        print(f"Available keys: {', '.join(KEY_MAP.keys())}")
        sys.exit(1)

    env_key = KEY_MAP[name]
    env = load_env()
    old = env.get(env_key, "(not set)")
    env[env_key] = value
    save_env(env)

    if env_key in SENSITIVE_KEYS:
        old = old[:8] + "..." if len(old) > 8 else old
        value = value[:8] + "..." if len(value) > 8 else value

    print(f"✓ {name}: {old} → {value}")


def cmd_start(args) -> None:
    """Start proxy servers."""
    env = load_env()
    ollama_port = env.get("OLLAMA_PORT", "4000")
    openrouter_port = env.get("OPENROUTER_PORT", "4001")

    script_dir = str(Path(__file__).parent)

    print("Starting Claude Provider Bridge…")
    print(f"  Ollama proxy     → http://localhost:{ollama_port}")
    print(f"  OpenRouter proxy → http://localhost:{openrouter_port}")
    print()

    procs = []
    try:
        p1 = subprocess.Popen(
            [sys.executable, os.path.join(script_dir, "ollama-proxy.py")],
            cwd=script_dir,
        )
        procs.append(("Ollama", p1))

        p2 = subprocess.Popen(
            [sys.executable, os.path.join(script_dir, "openrouter-proxy.py")],
            cwd=script_dir,
        )
        procs.append(("OpenRouter", p2))

        time.sleep(2)

        # Health checks
        import requests as req
        for name, port in [("Ollama", ollama_port), ("OpenRouter", openrouter_port)]:
            try:
                r = req.get(f"http://localhost:{port}/health", timeout=3)
                print(f"  ✓ {name} proxy healthy on port {port}")
            except Exception:
                print(f"  ✗ {name} proxy failed to start on port {port}")

        print("\nPress Ctrl+C to stop all proxies")
        # Cross-platform wait (signal.pause() is Unix-only)
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping proxies…")
        for name, p in procs:
            p.terminate()
        for name, p in procs:
            p.wait(timeout=5)
        print("Done!")


def cmd_switch(args) -> None:
    """Configure Claude Code to use a provider."""
    provider = args.provider.lower()
    env = load_env()

    if provider == "ollama":
        port = env.get("OLLAMA_PORT", "4000")
        model = env.get("OLLAMA_MODEL", "glm-5.1")
        display_model = f"ollama/{model}:cloud"
    elif provider == "openrouter":
        port = env.get("OPENROUTER_PORT", "4001")
        model = env.get("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        display_model = model
    else:
        print(f"Unknown provider: {provider}")
        print("Available: ollama, openrouter")
        sys.exit(1)

    settings_path = Path.home() / ".claude" / "settings.json"

    # Load existing settings if present, otherwise start fresh
    existing = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # Only update the env block, preserve everything else
    existing["env"] = {
        "ANTHROPIC_BASE_URL": f"http://localhost:{port}",
        "ANTHROPIC_AUTH_TOKEN": "sk-test",
        "ANTHROPIC_MODEL": display_model,
        "DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(existing, indent=2) + "\n")

    print(f"✓ Claude Code switched to {provider.title()} ({display_model})")
    print(f"  Base URL: http://localhost:{port}")
    print("  Run: claude")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bridge",
        description="Claude Provider Bridge — manage config and run proxies",
    )
    sub = parser.add_subparsers(dest="command")

    # config
    sub.add_parser("config", help="Show current configuration")

    # set
    p_set = sub.add_parser("set", help="Update a config value")
    p_set.add_argument("name", help=f"Config key: {', '.join(KEY_MAP.keys())}")
    p_set.add_argument("value", help="New value")

    # start
    sub.add_parser("start", help="Start all proxy servers")

    # switch
    p_switch = sub.add_parser("switch", help="Configure Claude Code for a provider")
    p_switch.add_argument("provider", choices=["ollama", "openrouter"], help="Provider to switch to")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    cmds = {
        "config": cmd_config,
        "set": cmd_set,
        "start": cmd_start,
        "switch": cmd_switch,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
