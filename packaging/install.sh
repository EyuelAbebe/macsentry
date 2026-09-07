#!/usr/bin/env bash
# Install sentinel as a launchd user agent on macOS.
# Run with: bash packaging/install.sh
set -euo pipefail

LABEL="com.macsentry.agent"
PLIST_SRC="$(cd "$(dirname "$0")" && pwd)/com.macsentry.agent.plist"
AGENTS_DIR="${HOME}/Library/LaunchAgents"
PLIST_DST="${AGENTS_DIR}/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/macsentry"

# ── resolve sentinel binary ───────────────────────────────────────────────────
SENTINEL_BIN="$(command -v sentinel 2>/dev/null || true)"
if [[ -z "${SENTINEL_BIN}" ]]; then
    # Try common Poetry/pip install locations
    for candidate in \
        "${HOME}/.local/bin/sentinel" \
        "${HOME}/.venv/bin/sentinel" \
        "$(python3 -m site --user-base 2>/dev/null)/bin/sentinel"
    do
        if [[ -x "${candidate}" ]]; then
            SENTINEL_BIN="${candidate}"
            break
        fi
    done
fi

if [[ -z "${SENTINEL_BIN}" ]]; then
    echo "ERROR: sentinel binary not found. Install it first:" >&2
    echo "  pip install macsentry[api]" >&2
    exit 1
fi

# ── prefer the Python-native CLI when available ───────────────────────────────
if command -v sentinel &>/dev/null; then
    echo "Delegating to: sentinel service install"
    sentinel service install
    exit $?
fi

# ── prepare directories ───────────────────────────────────────────────────────
mkdir -p "${AGENTS_DIR}" "${LOG_DIR}"

# ── substitute placeholders and write plist ───────────────────────────────────
sed \
    -e "s|SENTINEL_BIN|${SENTINEL_BIN}|g" \
    -e "s|SENTINEL_LOG_DIR|${LOG_DIR}|g" \
    -e "s|SENTINEL_USER|$(id -un)|g" \
    "${PLIST_SRC}" > "${PLIST_DST}"

echo "Wrote plist to: ${PLIST_DST}"

# ── unload previous instance if running ──────────────────────────────────────
if launchctl list "${LABEL}" &>/dev/null; then
    echo "Unloading previous instance..."
    launchctl unload "${PLIST_DST}" 2>/dev/null || true
fi

# ── load the agent ────────────────────────────────────────────────────────────
launchctl load "${PLIST_DST}"

echo ""
echo "Sentinel agent loaded. Status:"
launchctl list "${LABEL}" 2>/dev/null || echo "  (launchctl list returned no output — service may still be starting)"
echo ""
echo "Logs: ${LOG_DIR}/sentinel.log"
echo "API:  http://127.0.0.1:7173/health"
echo ""
echo "To uninstall: bash packaging/uninstall.sh"
