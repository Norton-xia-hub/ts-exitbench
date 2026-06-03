# ts-exitbench

Tailscale Exit Node speed selector.

This first version is a small Python tool for testing the connection from the
current Windows/macOS/Linux client to Linux nodes in your Tailscale network. It
ranks nodes by latency, route quality, download speed, and upload speed so you
can choose a better Exit Node for your current location.

## What it tests

- Tailscale peer discovery from `tailscale status --json`
- Latency and path hints from `tailscale ping`
- Agent health over the Tailscale IP
- Download speed: Linux node -> current client
- Upload speed: current client -> Linux node
- HTML and JSON reports

## Requirements

Client:

- Python 3.10+
- Tailscale installed and logged in
- `tailscale` command available in terminal

Linux nodes:

- Python 3.10+
- Tailscale installed and logged in
- Agent running on the Tailscale interface

## Quick start

Create a config from the example:

```bash
cp config.example.json config.json
```

On each Linux node, run the agent:

```bash
python3 -m ts_exitbench agent --config config.json
```

On your client machine, run:

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed
```

Open `report.html` in a browser.

## Install Linux agent as systemd service

Copy this project to the node, adjust paths in `packaging/ts-exitbench-agent.service`,
then run:

```bash
sudo cp packaging/ts-exitbench-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ts-exitbench-agent
```

## Config

`agent.token` must match between the client and every Linux agent.

Nodes are discovered automatically from Tailscale. The optional `nodes` section
adds friendly metadata and filtering. The key under `nodes` can match the
Tailscale host name, DNS name, or node name.
