from __future__ import annotations

import argparse
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import load_config, node_override
from .report import now_iso, write_html_report, write_json_report
from .tailscale import list_peers, ping

CHUNK = b"1" * 65536


def run_scan(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    scan_cfg = config["scan"]
    duration = int(args.duration or scan_cfg.get("duration_seconds", 30))
    concurrency = int(args.concurrency or scan_cfg.get("concurrency", 1))
    include_offline = bool(args.include_offline or scan_cfg.get("include_offline", False))
    timeout = float(scan_cfg.get("connect_timeout_seconds", 5))
    speed_enabled = bool(args.speed)

    self_node, peers = list_peers()
    selected = []
    for peer in peers:
        override = node_override(config, peer)
        if override.get("enabled") is False:
            continue
        if not include_offline and not peer.get("online"):
            continue
        peer["region"] = override.get("region") or override.get("location") or ""
        selected.append(peer)

    results = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = [pool.submit(scan_node, peer, config, duration, timeout, speed_enabled) for peer in selected]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.get("score", -1), reverse=True)
    for idx, result in enumerate(results, start=1):
        result["rank"] = idx

    report = {
        "generated_at": now_iso(),
        "client": {
            "host_name": (self_node or {}).get("HostName"),
            "dns_name": (self_node or {}).get("DNSName"),
        },
        "settings": {
            "duration_seconds": duration,
            "concurrency": concurrency,
            "speed_enabled": speed_enabled,
        },
        "nodes": results,
    }
    write_html_report(args.out, report)
    json_path = args.json_out or html_to_json_path(args.out)
    write_json_report(json_path, report)
    print(f"HTML report: {args.out}")
    print(f"JSON report: {json_path}")
    if results:
        best = results[0]
        print(f"Recommended exit node: {best.get('name')} ({best.get('score')} points)")
    return 0


def scan_node(peer: dict[str, Any], config: dict[str, Any], duration: int, timeout: float, speed_enabled: bool) -> dict[str, Any]:
    result = dict(peer)
    target = peer.get("ip") or peer.get("dns_name") or peer.get("name")
    if not target:
        result["error"] = "No Tailscale IP found"
        result["score"] = 0
        return result
    try:
        result["ping"] = ping(str(target))
    except Exception as exc:
        result["ping"] = {"ok": False, "error": str(exc), "path": "unknown", "avg_ms": None}
    agent = check_agent(str(target), config, timeout)
    result["agent"] = agent
    if speed_enabled and agent.get("ok"):
        result["download"] = download_speed(str(target), config, duration, timeout)
        result["upload"] = upload_speed(str(target), config, duration, timeout)
    result["score"] = score_node(result)
    return result


def base_url(target: str, config: dict[str, Any]) -> str:
    port = int(config["agent"].get("port", 51234))
    host = f"[{target}]" if ":" in target else target
    return f"http://{host}:{port}"


def request_headers(config: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {config['agent'].get('token', '')}"}


def check_agent(target: str, config: dict[str, Any], timeout: float) -> dict[str, Any]:
    req = Request(base_url(target, config) + "/health", headers=request_headers(config))
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"ok": bool(data.get("ok")), "status": resp.status}
    except (HTTPError, URLError, TimeoutError, socket.timeout, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def download_speed(target: str, config: dict[str, Any], duration: int, timeout: float) -> dict[str, Any]:
    query = urlencode({"duration": duration})
    req = Request(base_url(target, config) + f"/download?{query}", headers=request_headers(config))
    total = 0
    started = time.monotonic()
    try:
        with urlopen(req, timeout=timeout + duration + 5) as resp:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
    except Exception as exc:
        elapsed = max(time.monotonic() - started, 0.001)
        if total > 0:
            return speed_result(True, total, elapsed, warning=str(exc))
        return {"ok": False, "error": str(exc)}
    elapsed = max(time.monotonic() - started, 0.001)
    return speed_result(True, total, elapsed)


def upload_speed(target: str, config: dict[str, Any], duration: int, timeout: float) -> dict[str, Any]:
    port = int(config["agent"].get("port", 51234))
    token = config["agent"].get("token", "")
    total = 0
    started = time.monotonic()
    deadline = started + duration
    host_header = f"[{target}]" if ":" in target else target
    family = socket.AF_INET6 if ":" in target else socket.AF_INET
    request_head = (
        "POST /upload HTTP/1.1\r\n"
        f"Host: {host_header}:{port}\r\n"
        f"Authorization: Bearer {token}\r\n"
        "Content-Type: application/octet-stream\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((target, port))
            sock.settimeout(None)
            sock.sendall(request_head)
            while time.monotonic() < deadline:
                sock.sendall(CHUNK)
                total += len(CHUNK)
            sock.shutdown(socket.SHUT_WR)
            response = receive_response(sock)
    except Exception as exc:
        elapsed = max(time.monotonic() - started, 0.001)
        if total > 0:
            return speed_result(True, total, elapsed, warning=str(exc))
        return {"ok": False, "error": str(exc)}
    elapsed = max(time.monotonic() - started, 0.001)
    if not response.startswith("HTTP/1.1 200") and not response.startswith("HTTP/1.0 200"):
        return {"ok": False, "error": response.splitlines()[0] if response else "upload failed"}
    return speed_result(True, total, elapsed)


def receive_response(sock: socket.socket) -> str:
    chunks = []
    while True:
        data = sock.recv(4096)
        if not data:
            break
        chunks.append(data)
        if b"\r\n\r\n" in b"".join(chunks):
            break
    return b"".join(chunks).decode("iso-8859-1", errors="replace")


def speed_result(ok: bool, total: int, elapsed: float, warning: Optional[str] = None) -> dict[str, Any]:
    result = {
        "ok": ok,
        "bytes": total,
        "elapsed_seconds": round(elapsed, 3),
        "mbps": round((total * 8) / elapsed / 1_000_000, 2),
    }
    if warning:
        result["warning"] = warning
    return result


def score_node(node: dict[str, Any]) -> int:
    score = 0
    if node.get("online"):
        score += 10
    ping_data = node.get("ping", {})
    latency = ping_data.get("avg_ms")
    if latency is not None:
        score += max(0, int(40 - min(float(latency), 400) / 10))
    path = ping_data.get("path")
    if path == "direct":
        score += 20
    elif path in {"derp", "relay"}:
        score += 5
    for key in ("download", "upload"):
        speed = node.get(key) or {}
        if speed.get("ok"):
            score += min(40, int(float(speed.get("mbps", 0)) / 5))
    if not node.get("agent", {}).get("ok"):
        score -= 20
    return max(0, score)


def html_to_json_path(path: str) -> str:
    if path.lower().endswith(".html"):
        return path[:-5] + ".json"
    return path + ".json"
