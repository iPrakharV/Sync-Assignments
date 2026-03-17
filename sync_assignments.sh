#!/bin/bash

# Configuration
PROJECT_DIR="/Users/iprakharv/Developer/Sync-Assignments"
PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

# Navigate to project directory
cd "$PROJECT_DIR"

# Run the sync script
$PYTHON_BIN Main.py

# Check if the sync was successful (Main.py exit code)
if [ $? -eq 0 ]; then
    osascript -e 'display notification "Academic assignments synced successfully!" with title "Sync Assignments"'
else
    osascript -e 'display notification "Failed to sync academic assignments. Check logs." with title "Sync Assignments Error"'
fi
