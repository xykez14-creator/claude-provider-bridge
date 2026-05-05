#!/usr/bin/env python3
"""Claude Provider Bridge CLI — manage config and run proxies."""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
SCRIPT_DIR = str(Path(__file__).parent)

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

OLLAMA_KEYS = {"OLLAMA_KEY", "OLLAMA_URL", "OLLAMA_PORT", "OLLAMA_MODEL"}
OPENROUTER_KEYS = {"OPENROUTER_KEY", "OPENROUTER_URL", "OPENROUTER_PORT", "OPENROUTER_MODEL"}

# ---------------------------------------------------------------------------
# Claude settings helpers
# ---------------------------------------------------------------------------


def get_active_provider() -> str | None:
    """Read ~/.claude/settings.json and return the active provider name."""
    if not SETTINGS_PATH.exists():
        return None
    try:
        data = json.loads(SETTINGS_PATH.read_text())
        model = data.get("env", {}).get("ANTHROPIC_MODEL", "")
        if isinstance(model, str) and model.startswith("ollama/"):
            return "ollama"
        return "openrouter"
    except (json.JSONDecodeError, OSError):
        return None


def write_claude_settings(provider: str, env: dict) -> None:
    """Write Claude Code settings for the given provider."""
    if provider == "ollama":
        port = env.get("OLLAMA_PORT", "4000")
        model = env.get("OLLAMA_MODEL", "glm-5.1")
        display_model = f"ollama/{model}:cloud"
    elif provider == "openrouter":
        port = env.get("OPENROUTER_PORT", "4001")
        model = env.get("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        display_model = model
    else:
        return

    existing = {}
    if SETTINGS_PATH.exists():
        try:
            existing = json.loads(SETTINGS_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    existing["env"] = {
        "ANTHROPIC_BASE_URL": f"http://localhost:{port}",
        "ANTHROPIC_AUTH_TOKEN": "sk-test",
        "ANTHROPIC_MODEL": display_model,
        "DISABLE_TELEMETRY": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(existing, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Proxy process management
# ---------------------------------------------------------------------------


def find_proxy_pids(script_name: str) -> list[int]:
    """Return PIDs of running proxy processes by script name."""
    pids = []
    try:
        result = subprocess.run(
            ["pgrep", "-f", script_name],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    pids.append(int(line.strip()))
    except Exception:
        pass
    return pids


def kill_proxy(script_name: str) -> bool:
    """Kill all running instances of a proxy script. Returns True if any were killed."""
    pids = find_proxy_pids(script_name)
    killed = False
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            killed = True
        except ProcessLookupError:
            pass
    # Wait briefly for processes to terminate
    if killed:
        time.sleep(0.5)
    return killed


def start_proxy(script_name: str) -> subprocess.Popen | None:
    """Start a proxy in the background and return the Popen object."""
    try:
        return subprocess.Popen(
            [sys.executable, os.path.join(SCRIPT_DIR, script_name)],
            cwd=SCRIPT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None


def restart_proxy(provider: str) -> bool:
    """Kill and respawn a single proxy. Returns True on success."""
    script = "ollama-proxy.py" if provider == "ollama" else "openrouter-proxy.py"
    port_key = "OLLAMA_PORT" if provider == "ollama" else "OPENROUTER_PORT"
    env = load_env()
    port = env.get(port_key, "4000" if provider == "ollama" else "4001")

    was_running = bool(find_proxy_pids(script))
    kill_proxy(script)
    proc = start_proxy(script)
    if proc is None:
        return False

    # Health check
    time.sleep(1.5)
    try:
        import requests as req
        resp = req.get(f"http://localhost:{port}/health", timeout=3)
        if resp.status_code == 200:
            if was_running:
                print(f"  ♻ {provider.title()} proxy restarted on port {port}")
            else:
                print(f"  ✓ {provider.title()} proxy started on port {port}")
            return True
    except Exception:
        pass

    print(f"  ✗ {provider.title()} proxy failed health check on port {port}")
    return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_config(_args) -> None:
    """Show current configuration."""
    env = load_env()
    if not env:
        print("No .env file found. Run:  cp .env.example .env")
        sys.exit(1)

    active = get_active_provider()
    print("Claude Provider Bridge — Current Config")
    print("=" * 42)
    for cli_name, env_key in KEY_MAP.items():
        val = env.get(env_key, "(not set)")
        if env_key in SENSITIVE_KEYS and val != "(not set)":
            val = val[:8] + "..." + val[-4:]
        print(f"  {cli_name:20s} {val}")
    print()
    if active:
        print(f"  Active provider:      {active}")
    else:
        print("  Active provider:      (not configured — run: bridge.py switch <provider>)")
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

    # Auto-sync Claude settings when the changed key belongs to the active provider
    active = get_active_provider()
    synced_provider = None
    if active == "ollama" and env_key in OLLAMA_KEYS:
        write_claude_settings("ollama", env)
        print(f"✓ Claude Code config auto-updated (active provider: ollama)")
        synced_provider = "ollama"
    elif active == "openrouter" and env_key in OPENROUTER_KEYS:
        write_claude_settings("openrouter", env)
        print(f"✓ Claude Code config auto-updated (active provider: openrouter)")
        synced_provider = "openrouter"
    else:
        if active:
            print(f"  (Claude Code config unchanged — active provider is {active})")
        else:
            print("  (Claude Code config unchanged — run: bridge.py switch <provider>)")

    # Auto-restart affected proxy so new .env values are picked up
    restarted = False
    if env_key in OLLAMA_KEYS:
        restarted = restart_proxy("ollama")
    elif env_key in OPENROUTER_KEYS:
        restarted = restart_proxy("openrouter")

    if restarted and synced_provider:
        print(f"  Ready to use with: claude")


def cmd_start(args) -> None:
    """Start proxy servers."""
    env = load_env()
    ollama_port = env.get("OLLAMA_PORT", "4000")
    openrouter_port = env.get("OPENROUTER_PORT", "4001")

    print("Starting Claude Provider Bridge…")
    print(f"  Ollama proxy     → http://localhost:{ollama_port}")
    print(f"  OpenRouter proxy → http://localhost:{openrouter_port}")
    print()

    procs = []
    try:
        p1 = subprocess.Popen(
            [sys.executable, os.path.join(SCRIPT_DIR, "ollama-proxy.py")],
            cwd=SCRIPT_DIR,
        )
        procs.append(("Ollama", p1))

        p2 = subprocess.Popen(
            [sys.executable, os.path.join(SCRIPT_DIR, "openrouter-proxy.py")],
            cwd=SCRIPT_DIR,
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


def cmd_stop(args) -> None:
    """Stop proxy servers."""
    ollama_killed = kill_proxy("ollama-proxy.py")
    openrouter_killed = kill_proxy("openrouter-proxy.py")

    if ollama_killed or openrouter_killed:
        print("✓ Proxies stopped")
    else:
        print("(no proxies were running)")


def cmd_restart(args) -> None:
    """Restart proxy servers."""
    provider = args.provider.lower() if args.provider else None

    if provider == "ollama":
        restart_proxy("ollama")
    elif provider == "openrouter":
        restart_proxy("openrouter")
    elif provider is None:
        restart_proxy("ollama")
        restart_proxy("openrouter")
    else:
        print(f"Unknown provider: {provider}")
        print("Available: ollama, openrouter (or omit to restart both)")
        sys.exit(1)


def cmd_switch(args) -> None:
    """Configure Claude Code to use a provider."""
    provider = args.provider.lower()
    env = load_env()

    if provider not in ("ollama", "openrouter"):
        print(f"Unknown provider: {provider}")
        print("Available: ollama, openrouter")
        sys.exit(1)

    write_claude_settings(provider, env)

    if provider == "ollama":
        port = env.get("OLLAMA_PORT", "4000")
        model = env.get("OLLAMA_MODEL", "glm-5.1")
        display_model = f"ollama/{model}:cloud"
    else:
        port = env.get("OPENROUTER_PORT", "4001")
        model = env.get("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        display_model = model

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

    # stop
    sub.add_parser("stop", help="Stop all proxy servers")

    # restart
    p_restart = sub.add_parser("restart", help="Restart proxy servers")
    p_restart.add_argument("provider", nargs="?", choices=["ollama", "openrouter"],
                           help="Provider to restart (omit for both)")

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
        "stop": cmd_stop,
        "restart": cmd_restart,
        "switch": cmd_switch,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
