from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def write_json_report(path: str, report: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html_report(path: str, report: dict[str, Any]) -> None:
    rows = "\n".join(render_row(node) for node in report["nodes"])
    generated = html.escape(report.get("generated_at", ""))
    source = html.escape(report.get("client", {}).get("host_name", "current client"))
    body = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ts-exitbench report</title>
<style>
:root {{ color-scheme: light; --ok:#137333; --bad:#b3261e; --muted:#5f6368; --line:#dadce0; --bg:#f8fafc; }}
body {{ margin:0; font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#202124; background:var(--bg); }}
main {{ max-width:1180px; margin:0 auto; padding:28px 20px 44px; }}
h1 {{ margin:0 0 8px; font-size:28px; }}
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:22px 0; }}
.metric {{ background:white; border:1px solid var(--line); border-radius:8px; padding:14px; }}
.metric strong {{ display:block; font-size:24px; }}
table {{ width:100%; border-collapse:collapse; background:white; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
th {{ background:#eef2f7; font-size:12px; color:#3c4043; text-transform:uppercase; }}
tr:last-child td {{ border-bottom:0; }}
.badge {{ display:inline-block; border-radius:999px; padding:2px 8px; font-size:12px; background:#eef2f7; }}
.ok {{ color:var(--ok); font-weight:600; }} .bad {{ color:var(--bad); font-weight:600; }} .muted {{ color:var(--muted); }}
.score {{ font-weight:700; font-size:18px; }}
.error {{ color:var(--bad); max-width:260px; overflow-wrap:anywhere; }}
</style>
</head>
<body><main>
<h1>Tailscale Exit Node Speed Report</h1>
<div class="muted">Client: {source} · Generated: {generated}</div>
{render_summary(report)}
<table>
<thead><tr><th>Rank</th><th>Node</th><th>Region</th><th>Status</th><th>Ping</th><th>Download</th><th>Upload</th><th>Score</th><th>Notes</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</main></body></html>"""
    Path(path).write_text(body, encoding="utf-8")


def render_summary(report: dict[str, Any]) -> str:
    nodes = report["nodes"]
    tested = [n for n in nodes if n.get("agent", {}).get("ok")]
    best = nodes[0] if nodes else None
    best_name = best.get("name") if best else "-"
    direct = sum(1 for n in nodes if n.get("ping", {}).get("path") == "direct")
    return f"""<section class="summary">
<div class="metric"><span class="muted">Nodes</span><strong>{len(nodes)}</strong></div>
<div class="metric"><span class="muted">Speed tested</span><strong>{len(tested)}</strong></div>
<div class="metric"><span class="muted">Direct path</span><strong>{direct}</strong></div>
<div class="metric"><span class="muted">Recommended</span><strong>{html.escape(str(best_name))}</strong></div>
</section>"""


def render_row(node: dict[str, Any]) -> str:
    rank = node.get("rank", "-")
    name = html.escape(str(node.get("name") or "-"))
    ip = html.escape(str(node.get("ip") or "-"))
    region = html.escape(str(node.get("region") or "-"))
    online = "online" if node.get("online") else "offline"
    online_cls = "ok" if node.get("online") else "bad"
    ping = node.get("ping", {})
    ping_text = "-"
    if ping.get("avg_ms") is not None:
        ping_text = f"{ping['avg_ms']} ms · {html.escape(str(ping.get('path', 'unknown')))}"
    down = speed_cell(node.get("download"))
    up = speed_cell(node.get("upload"))
    score = node.get("score")
    score_text = f"<span class=\"score\">{score}</span>" if score is not None else "-"
    notes = html.escape(str(node.get("error") or node.get("agent", {}).get("error") or ""))
    return f"""<tr>
<td>{rank}</td><td><strong>{name}</strong><br><span class="muted">{ip}</span></td><td>{region}</td>
<td><span class="{online_cls}">{online}</span></td><td>{ping_text}</td><td>{down}</td><td>{up}</td><td>{score_text}</td><td class="error">{notes}</td>
</tr>"""


def speed_cell(speed: Optional[dict[str, Any]]) -> str:
    if not speed:
        return "-"
    if not speed.get("ok"):
        return f"<span class=\"bad\">failed</span><br><span class=\"error\">{html.escape(str(speed.get('error', '')))}</span>"
    return f"<span class=\"ok\">{speed.get('mbps')} Mbps</span><br><span class=\"muted\">{speed.get('bytes', 0):,} bytes</span>"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
