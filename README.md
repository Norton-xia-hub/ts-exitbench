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

- Python 3.9+
- Tailscale installed and logged in
- `tailscale` command available in terminal

Linux nodes:

- Python 3.9+
- Tailscale installed and logged in
- Agent bound to the node's Tailscale IP

## Quick start

Create a client config from the example:

```bash
cp config.example.json config.json
```

Set the shared `agent.token` value in `config.json`, then run from your client:

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed
```

Open `report.html` in a browser.

## Install Linux agent

Run this inside the repo on each Linux node:

```bash
sudo ./install-agent.sh
```

The installer will:

- copy the project to `/opt/ts-exitbench`
- detect the node's Tailscale IPv4 with `tailscale ip -4`
- create `/etc/ts-exitbench/config.json` on first install
- bind the agent to the Tailscale IP instead of `0.0.0.0`
- install and start `ts-exitbench-agent.service`

If you want to set the token yourself during install:

```bash
sudo TS_EXITBENCH_TOKEN='your-shared-token' ./install-agent.sh
```

## Manual agent run

On a Linux node:

```bash
python3 -m ts_exitbench agent --config /etc/ts-exitbench/config.json
```

## Config

`agent.token` must match between the client and every Linux agent.

In the example config, set `agent.host` to the node's Tailscale IPv4. You can
get it with:

```bash
tailscale ip -4
```

Nodes are discovered automatically from Tailscale. The optional `nodes` section
adds friendly metadata and filtering. The key under `nodes` can match the
Tailscale host name, DNS name, or node name.
