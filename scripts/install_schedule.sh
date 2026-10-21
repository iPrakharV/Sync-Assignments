#!/bin/bash
# Runs Sync Assignments automatically via launchd (macOS). If the Mac is asleep at a
# scheduled time, launchd runs the job once when it wakes up.
#   scripts/install_schedule.sh            install / update (default: 8:00 and 20:00)
#   scripts/install_schedule.sh 7 13 21    install with custom hours
#   scripts/install_schedule.sh --remove   uninstall
set -euo pipefail

LABEL="com.syncassignments.sync"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO/.venv/bin/python"

if [[ "${1:-}" == "--remove" ]]; then
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Removed $LABEL."
    exit 0
fi

[[ -x "$PYTHON" ]] || { echo "No virtualenv at $REPO/.venv — create it and pip install -r requirements.txt first."; exit 1; }

HOURS=("$@")
[[ ${#HOURS[@]} -eq 0 ]] && HOURS=(8 20)
INTERVALS=""
for hour in "${HOURS[@]}"; do
    INTERVALS+="        <dict><key>Hour</key><integer>$hour</integer><key>Minute</key><integer>0</integer></dict>"$'\n'
done

mkdir -p "$REPO/logs" "$(dirname "$PLIST")"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$REPO/Main.py</string>
        <string>--scheduled</string>
    </array>
    <key>WorkingDirectory</key><string>$REPO</string>
    <key>StartCalendarInterval</key>
    <array>
$INTERVALS    </array>
    <key>StandardOutPath</key><string>$REPO/logs/launchd.out.log</string>
    <key>StandardErrorPath</key><string>$REPO/logs/launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL — runs daily at: $(printf '%s:00 ' "${HOURS[@]}")"
echo "Run it right now with: launchctl kickstart gui/$(id -u)/$LABEL"
