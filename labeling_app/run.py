#!/usr/bin/env python3
"""KCMS Collaborative Labeler Launcher.

Starts the FastAPI server, automatically checks for Cloudflare Tunnel,
and displays shareable local and public HTTPS links for multi-annotator sync.
"""

from __future__ import annotations

import atexit
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import uvicorn

# Global handle for tunnel process
_tunnel_proc: subprocess.Popen | None = None


def cleanup_tunnel():
    global _tunnel_proc
    if _tunnel_proc and _tunnel_proc.poll() is None:
        try:
            _tunnel_proc.terminate()
            _tunnel_proc.wait(timeout=2)
        except Exception:
            try:
                _tunnel_proc.kill()
            except Exception:
                pass


atexit.register(cleanup_tunnel)


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_cloudflare_tunnel(port: int) -> str | None:
    """Check for Cloudflare and start tunnel if available, returning the public URL."""
    global _tunnel_proc

    cmd = None
    if shutil.which("cloudflared"):
        cmd = ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"]
    elif shutil.which("npx"):
        cmd = ["npx", "-y", "cloudflared", "tunnel", "--url", f"http://localhost:{port}"]

    if not cmd:
        return None

    try:
        _tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Listen for trycloudflare.com URL in a short window (up to 7 seconds)
        public_url = None
        start_time = time.time()
        while time.time() - start_time < 7:
            if _tunnel_proc.poll() is not None:
                break
            line = _tunnel_proc.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
            m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if m:
                public_url = m.group(0)
                break

        # Start a daemon thread to drain remaining output so buffers don't fill
        def _drain():
            if _tunnel_proc and _tunnel_proc.stdout:
                for _ in _tunnel_proc.stdout:
                    pass

        threading.Thread(target=_drain, daemon=True).start()
        return public_url
    except Exception as e:
        print(f"[Warning] Could not start Cloudflare tunnel: {e}")
        return None


def main():
    port = 8000
    local_ip = get_local_ip()
    app_dir = Path(__file__).resolve().parent

    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    print("\n🔍 Checking for Cloudflare Tunnel...")
    cloudflare_installed = bool(shutil.which("cloudflared") or shutil.which("npx"))

    public_url = None
    if cloudflare_installed:
        print("⚡ Cloudflare detected! Launching secure public tunnel for your friends...")
        public_url = start_cloudflare_tunnel(port)
    else:
        print("ℹ️ Cloudflare not found (install via 'brew install cloudflared' or Node.js).")

    print("\n" + "=" * 70)
    print("🛡️   KCMS COLLABORATIVE DATA LABELER")
    print("=" * 70)
    print(f"\n1. Open on your computer:")
    print(f"   👉 http://localhost:{port}")
    print(f"\n2. Share with friends on same Wi-Fi / Local Network:")
    print(f"   👉 http://{local_ip}:{port}")

    if public_url:
        print(f"\n3. 🌐 PUBLIC SHAREABLE LINK (Send to friends anywhere in the world):")
        print(f"   👉 {public_url}")
        print(f"   (No login needed — anyone with this link can label!)")
    else:
        print(f"\n3. 🌐 Share over Internet:")
        print(f"   To generate a public link, install cloudflared or run:")
        print(f"   👉 npx -y cloudflared tunnel --url http://localhost:{port}")

    print("\n" + "-" * 70)
    print("All annotations sync directly to:")
    print("  • scraper/raw_data/cleaned_comments.csv")
    print("  • ai_engine/data/comments.csv")
    print("=" * 70 + "\n")

    try:
        uvicorn.run("server:app", app_dir=str(app_dir), host="0.0.0.0", port=port, reload=True)
    finally:
        cleanup_tunnel()


if __name__ == "__main__":
    main()
