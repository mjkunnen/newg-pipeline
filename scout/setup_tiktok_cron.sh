#!/bin/bash
# Setup daily TikTok Carousel Checker cron job on VPS.
# Run once: bash scout/setup_tiktok_cron.sh

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(which python3)"
SCRIPT="scout/tiktok_checker.py"
LOG="$REPO_DIR/logs/tiktok-cron.log"

# Add cron job: daily at 10:00 UTC
CRON_LINE="0 10 * * * cd $REPO_DIR && $PYTHON $SCRIPT >> $LOG 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "tiktok_checker"; then
    echo "Cron job already exists. Current entry:"
    crontab -l | grep "tiktok_checker"
    echo ""
    echo "To replace, run: crontab -e"
else
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "Cron job installed:"
    echo "  $CRON_LINE"
    echo ""
    echo "Verify with: crontab -l"
fi
