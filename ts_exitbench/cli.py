from __future__ import annotations

import argparse
from typing import Optional

from .agent import run_agent
from .scanner import run_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ts-exitbench", description="Tailscale Exit Node speed selector")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="scan Tailscale peers and generate a report")
    scan.add_argument("--config", default="config.json", help="config JSON path")
    scan.add_argument("--out", default="report.html", help="HTML report path")
    scan.add_argument("--json-out", help="JSON report path")
    scan.add_argument("--duration", type=int, help="speed test duration per direction")
    scan.add_argument("--concurrency", type=int, help="number of nodes to test at once")
    scan.add_argument("--include-offline", action="store_true", help="include offline nodes in report")
    scan.add_argument("--speed", action="store_true", help="run upload and download speed tests")
    scan.set_defaults(func=run_scan)

    agent = sub.add_parser("agent", help="run the Linux node agent")
    agent.add_argument("--config", default="config.json", help="config JSON path")
    agent.add_argument("--host", help="listen host")
    agent.add_argument("--port", type=int, help="listen port")
    agent.add_argument("--token", help="auth token")
    agent.add_argument("--quiet", action="store_true", help="suppress HTTP access logs")
    agent.set_defaults(func=run_agent)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
