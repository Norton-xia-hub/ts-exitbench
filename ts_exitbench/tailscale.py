from __future__ import annotations

import json
import re
import subprocess
from typing import Any


LATENCY_RE = re.compile(r"time=([0-9.]+)ms")


def run_tailscale(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["tailscale", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def status() -> dict[str, Any]:
    proc = run_tailscale(["status", "--json"], timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "tailscale status failed")
    return json.loads(proc.stdout)


def list_peers() -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    data = status()
    self_node = data.get("Self")
    peers = []
    for peer in (data.get("Peer") or {}).values():
        ips = peer.get("TailscaleIPs") or []
        peers.append({
            "id": peer.get("ID"),
            "name": peer.get("Name") or peer.get("DNSName") or peer.get("HostName"),
            "dns_name": peer.get("DNSName"),
            "host_name": peer.get("HostName"),
            "os": peer.get("OS"),
            "online": bool(peer.get("Online")),
            "tailscale_ips": ips,
            "ip": next((ip for ip in ips if "." in ip), ips[0] if ips else None),
            "exit_node": bool(peer.get("ExitNode")),
            "exit_node_option": bool(peer.get("ExitNodeOption")),
        })
    return self_node, peers


def ping(target: str) -> dict[str, Any]:
    proc = run_tailscale(["ping", "--c", "3", target], timeout=20)
    output = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
    latency_values = [float(match) for match in LATENCY_RE.findall(output)]
    avg = round(sum(latency_values) / len(latency_values), 2) if latency_values else None
    lower = output.lower()
    path = "unknown"
    if "direct" in lower:
        path = "direct"
    elif "derp" in lower:
        path = "derp"
    elif "relay" in lower:
        path = "relay"
    return {
        "ok": proc.returncode == 0,
        "avg_ms": avg,
        "path": path,
        "raw": output.strip()[-1000:],
    }
