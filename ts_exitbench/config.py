import json
from pathlib import Path
from typing import Any, Optional


DEFAULT_CONFIG: dict[str, Any] = {
    "agent": {
        "host": "0.0.0.0",
        "port": 51234,
        "token": "change-me",
    },
    "scan": {
        "duration_seconds": 30,
        "concurrency": 1,
        "include_offline": False,
        "connect_timeout_seconds": 5,
    },
    "nodes": {},
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Optional[str]) -> dict[str, Any]:
    if not path:
        return DEFAULT_CONFIG
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return deep_merge(DEFAULT_CONFIG, data)


def node_override(config: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    names = [
        node.get("host_name"),
        node.get("dns_name"),
        node.get("name"),
    ]
    short_dns = (node.get("dns_name") or "").split(".")[0]
    if short_dns:
        names.append(short_dns)
    nodes = config.get("nodes", {})
    for name in names:
        if name and name in nodes:
            return nodes[name]
    return {}
