#!/bin/bash

# Configuration
PROJECT_DIR="/Users/iprakharv/Developer/Sync-Assignments"
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

# Navigate to project directory
cd "$PROJECT_DIR"

# Run the sync script and capture output
SYNC_OUTPUT=$($PYTHON_BIN Main.py)
EXIT_CODE=$?

# Extract synced tasks from output
SYNCED_TASKS=$(echo "$SYNC_OUTPUT" | grep "SYNCED_TASKS_DATA:" | cut -d':' -f2- | xargs)

# Check if the sync was successful
if [ $EXIT_CODE -eq 0 ]; then
    if [ "$SYNCED_TASKS" != "None" ] && [ -n "$SYNCED_TASKS" ]; then
        osascript -e "display notification \"$SYNCED_TASKS\" with title \"Synced Assignments\""
    else
        osascript -e 'display notification "No new tasks synced today." with title "Sync Assignments"'
    fi
else
    osascript -e 'display notification "Failed to sync academic assignments. Check logs." with title "Sync Assignments Error"'
fi
