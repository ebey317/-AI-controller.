#!/bin/bash
# update.sh — Check for AI Controller updates and install the latest release.
#
# The buyer's archive ships with this script. It polls a public release URL
# (configured in ~/.config/ai_controller_update_url) for a version file,
# downloads the matching archive if newer, and restarts services.
#
# Default release host: a public GitHub repo or any HTTPS file server.

set -euo pipefail

INSTALL_DIR="${AI_CONTROLLER_DIR:-$HOME/-AI-controller.}"
UPDATE_URL="${AI_CONTROLLER_UPDATE_URL:-}"
STATE_FILE="$HOME/.config/ai_controller_version"

if [ -z "$UPDATE_URL" ]; then
    echo "No update URL configured."
    echo "Set AI_CONTROLLER_UPDATE_URL or put it in ~/.config/ai_controller_update_url"
    exit 1
fi

# Allow override from config file
if [ -f "$HOME/.config/ai_controller_update_url" ]; then
    UPDATE_URL=$(cat "$HOME/.config/ai_controller_update_url" | tr -d '[:space:]')
fi

VERSION_URL="$UPDATE_URL/VERSION"
ARCHIVE_URL="$UPDATE_URL/ai-controller-latest.tar.gz"

echo "Checking for updates from $VERSION_URL ..."

LOCAL_VERSION="0.0.0"
if [ -f "$INSTALL_DIR/VERSION" ]; then
    LOCAL_VERSION=$(cat "$INSTALL_DIR/VERSION" | tr -d '[:space:]')
elif [ -f "$STATE_FILE" ]; then
    LOCAL_VERSION=$(cat "$STATE_FILE" | tr -d '[:space:]')
fi

REMOTE_VERSION=$(curl -fsSL "$VERSION_URL" | tr -d '[:space:]' || true)
if [ -z "$REMOTE_VERSION" ]; then
    echo "Could not fetch remote version. Update server may be down."
    exit 1
fi

echo "Local version: $LOCAL_VERSION"
echo "Remote version: $REMOTE_VERSION"

if [ "$LOCAL_VERSION" = "$REMOTE_VERSION" ]; then
    echo "Already up to date."
    exit 0
fi

# Download update to temp location
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

echo "Downloading $ARCHIVE_URL ..."
curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/ai-controller-$REMOTE_VERSION.tar.gz"

echo "Installing update ..."
# Extract next to the current install, then atomically swap
BACKUP_DIR="$INSTALL_DIR.backup.$(date +%s)"
NEW_DIR="$INSTALL_DIR.new"
rm -rf "$NEW_DIR"
mkdir -p "$NEW_DIR"
tar -xzf "$TMP_DIR/ai-controller-$REMOTE_VERSION.tar.gz" -C "$NEW_DIR" --strip-components=1

# Preserve buyer-specific state
for f in "$INSTALL_DIR/config/ptt_mode" "$INSTALL_DIR/config/ptt_vocabulary.json" "$HOME/.config/ai_controller_voice" "$HOME/.config/ai_controller_unlocked_voices.json"; do
    if [ -f "$f" ]; then
        cp -p "$f" "$NEW_DIR/$(basename "$f")" 2>/dev/null || true
    fi
done

mv "$INSTALL_DIR" "$BACKUP_DIR"
mv "$NEW_DIR" "$INSTALL_DIR"

echo "$REMOTE_VERSION" > "$STATE_FILE"

echo "Updated to $REMOTE_VERSION. Backup at $BACKUP_DIR"
echo "Restarting services ..."
systemctl --user restart voice-bridge.service ptt-pynput.service antimicrox-autoload.service 2>/dev/null || true

echo "Done."
