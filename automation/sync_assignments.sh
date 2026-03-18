#!/bin/bash

# Configuration
PROJECT_DIR="/Users/iprakharv/Developer/Sync-Assignments"
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
STATE_FILE="$HOME/.sync_assignments_last_run"

# Navigate to project directory
cd "$PROJECT_DIR"

# Get current date and hour
CURRENT_DATE=$(date +%Y-%m-%d)
CURRENT_HOUR=$(date +%k) # %k is hour (0..23), space padded

# Check if it's at least 6 AM
if [ "${CURRENT_HOUR// /}" -lt 6 ]; then
    echo "Current hour is $CURRENT_HOUR. Skipping sync until after 6 AM."
    exit 0
fi

# Check if we already ran today
if [ -f "$STATE_FILE" ]; then
    LAST_RUN=$(cat "$STATE_FILE")
    if [ "$LAST_RUN" == "$CURRENT_DATE" ]; then
        echo "Already ran today ($CURRENT_DATE). Skipping sync."
        exit 0
    fi
fi

# Run the sync script and capture output
SYNC_OUTPUT=$($PYTHON_BIN Main.py)
EXIT_CODE=$?

# Extract synced tasks from output
SYNCED_TASKS=$(echo "$SYNC_OUTPUT" | grep "SYNCED_TASKS_DATA:" | cut -d':' -f2- | xargs)

# Check if the sync was successful
if [ $EXIT_CODE -eq 0 ]; then
    # Update last run date
    echo "$CURRENT_DATE" > "$STATE_FILE"
    
    if [ "$SYNCED_TASKS" != "None" ] && [ -n "$SYNCED_TASKS" ]; then
        osascript -e "display notification \"$SYNCED_TASKS\" with title \"Synced Assignments\""
    else
        osascript -e 'display notification "No new tasks synced today." with title "Sync Assignments"'
    fi
else
    osascript -e 'display notification "Failed to sync academic assignments. Check logs." with title "Sync Assignments Error"'
fi
