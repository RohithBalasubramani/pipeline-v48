#!/usr/bin/env bash
# install-units.sh — install/refresh every V48 user-level service unit. [audit R4 2026-07-12]
# System-level units (db-tunnel.service — needs root; vllm.service — GPU model) are NOT touched here:
#   sudo cp ops/db-tunnel.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart db-tunnel
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ~/.config/systemd/user
cp v48-host.service v48-admin.service v48-web.service ~/.config/systemd/user/
cp ../copilot/deploy/ems-copilot.service ../copilot/deploy/vllm-copilot.service ~/.config/systemd/user/ 2>/dev/null || true
systemctl --user daemon-reload
echo "Installed. Enable with:"
echo "  systemctl --user enable --now v48-host v48-admin v48-web ems-copilot vllm-copilot"
echo "NOTE: services currently hand-run in terminals will conflict on their ports — stop those first."
