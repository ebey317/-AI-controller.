#!/usr/bin/env bash
# install.sh — AI Controller systemd user-service installer
# Run once after cloning: bash install.sh
# Sets the controller up to survive reboots and power loss.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICES=(
    antimicrox-autoload.service
    controller-legend.service
    ptt-pynput.service
    voice-bridge.service
)

echo "Installing AI Controller systemd user services..."
echo "Repo: ${REPO_DIR}"

mkdir -p "${SERVICE_DIR}"

for svc in "${SERVICES[@]}"; do
    src="${REPO_DIR}/systemd/${svc}"
    dst="${SERVICE_DIR}/${svc}"
    if [[ ! -f "${src}" ]]; then
        echo "ERROR: missing ${src}" >&2
        exit 1
    fi
    cp -v "${src}" "${dst}"
done

# Reload systemd user daemon and enable services.
systemctl --user daemon-reload
for svc in "${SERVICES[@]}"; do
    systemctl --user enable "${svc}"
done

echo ""
echo "Services installed and enabled. Starting now..."
for svc in "${SERVICES[@]}"; do
    systemctl --user restart "${svc}" || true
done

echo ""
echo "Done. The AI Controller will start automatically on login."
echo "Check status with: systemctl --user status ${SERVICES[*]}"
