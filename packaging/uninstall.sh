#!/usr/bin/env bash
# Uninstall the macsentry launchd user agent on macOS.
# Run with: bash packaging/uninstall.sh
set -euo pipefail

LABEL="com.macsentry.agent"
PLIST_DST="${HOME}/Library/LaunchAgents/${LABEL}.plist"

# ── prefer the Python-native CLI when available ───────────────────────────────
for name in macsentry sentinel; do
    if command -v "${name}" &>/dev/null; then
        echo "Delegating to: ${name} service uninstall"
        "${name}" service uninstall
        exit $?
    fi
done

if [[ ! -f "${PLIST_DST}" ]]; then
    echo "Plist not found at ${PLIST_DST} — nothing to uninstall."
    exit 0
fi

# Unload if running
if launchctl list "${LABEL}" &>/dev/null; then
    echo "Stopping and unloading ${LABEL}..."
    launchctl unload "${PLIST_DST}"
fi

rm -f "${PLIST_DST}"
echo "Removed: ${PLIST_DST}"
echo "MacSentry launchd agent uninstalled."
