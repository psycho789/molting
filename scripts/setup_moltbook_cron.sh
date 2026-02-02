#!/bin/bash
# Setup script for moltbook cronjob
# This creates a cronjob that runs every hour and creates a new post or comments
# Posts/comments are generated with random topics in the ribbons personality style

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CRON_SCRIPT="$PROJECT_DIR/src/moltbook_cron.py"
PYTHON_PATH="$(which python3)"

# Check if Python script exists
if [ ! -f "$CRON_SCRIPT" ]; then
    echo "Error: $CRON_SCRIPT not found"
    exit 1
fi

# Create cronjob entry (runs every hour at minute 0)
# Note: Make sure to activate venv if using one
if [ -d "$PROJECT_DIR/venv" ]; then
    CRON_ENTRY="0 * * * * cd $PROJECT_DIR && source venv/bin/activate && $PYTHON_PATH $CRON_SCRIPT >> $PROJECT_DIR/logs/moltbook_cron.log 2>&1"
else
    CRON_ENTRY="0 * * * * cd $PROJECT_DIR && $PYTHON_PATH $CRON_SCRIPT >> $PROJECT_DIR/logs/moltbook_cron.log 2>&1"
fi

# Check if cronjob already exists
if crontab -l 2>/dev/null | grep -q "moltbook_cron.py"; then
    echo "Cronjob already exists. Removing old entry..."
    crontab -l 2>/dev/null | grep -v "moltbook_cron.py" | crontab -
fi

# Add new cronjob
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✓ Cronjob installed successfully"
echo "  Runs every hour (at minute 0)"
echo "  50% chance: Comments on existing posts (brief, original personality)"
echo "  50% chance: Creates new posts with topics (wordy, moltbook personality)"
echo "  Logs to: $PROJECT_DIR/logs/moltbook_cron.log"
echo ""
echo "Configure submolts in config.json under moltbook.submolts"
echo "To view current cronjobs: crontab -l"
echo "To remove this cronjob: crontab -e (then delete the line)"
