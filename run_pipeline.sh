#!/bin/bash
# ==============================================================================
# Stock Discovery & Portfolio Rebalancing Scheduler Execution Script (Linux)
# ==============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_DIR/venv"
LOGS_DIR="$PROJECT_DIR/logs"

cd "$PROJECT_DIR"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Stock Discovery Pipeline run on Linux..." >> "$LOGS_DIR/scheduler.log"

# Check if virtual environment exists, if not create it
if [ ! -d "$VENV_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Virtual environment not found. Creating one..." >> "$LOGS_DIR/scheduler.log"
    python3 -m venv "$VENV_DIR" >> "$LOGS_DIR/scheduler.log" 2>&1
    if [ $? -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Failed to create virtual environment." >> "$LOGS_DIR/scheduler.log"
        exit 1
    fi
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate" >> "$LOGS_DIR/scheduler.log" 2>&1

# Install/verify dependencies
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Verifying dependencies..." >> "$LOGS_DIR/scheduler.log"
pip install --upgrade pip >> "$LOGS_DIR/scheduler.log" 2>&1
pip install -r "$PROJECT_DIR/requirements.txt" >> "$LOGS_DIR/scheduler.log" 2>&1
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Failed to verify or install dependencies. Proceeding with existing packages." >> "$LOGS_DIR/scheduler.log"
fi

# Run the orchestrator script
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing main.py..." >> "$LOGS_DIR/scheduler.log"
python3 "$PROJECT_DIR/main.py" >> "$LOGS_DIR/scheduler.log" 2>&1

PIPELINE_STATUS=$?
if [ $PIPELINE_STATUS -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: main.py execution failed with exit code $PIPELINE_STATUS." >> "$LOGS_DIR/scheduler.log"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline executed successfully." >> "$LOGS_DIR/scheduler.log"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pipeline run finished." >> "$LOGS_DIR/scheduler.log"
echo "--------------------------------------------------" >> "$LOGS_DIR/scheduler.log"

deactivate
exit $PIPELINE_STATUS
