#!/bin/bash
# Start pre-earnings agent in a tmux session
# Usage: bash deploy/tmux_start.sh

SESSION="pre-earnings"
AGENT_DIR="/Users/lukenmark/Documents/claude-os/tools/pre-earnings-agent"

# Ensure logs directory exists
mkdir -p "$AGENT_DIR/logs"

# Kill existing session if running
tmux kill-session -t "$SESSION" 2>/dev/null

# Create new session with two windows
tmux new-session -d -s "$SESSION" -n "agent" -c "$AGENT_DIR"
tmux send-keys -t "$SESSION:agent" "python3 run.py start" Enter

# Second window for dashboard
tmux new-window -t "$SESSION" -n "dashboard" -c "$AGENT_DIR"
tmux send-keys -t "$SESSION:dashboard" "python3 run.py dashboard" Enter

# Third window for logs
tmux new-window -t "$SESSION" -n "logs" -c "$AGENT_DIR"
tmux send-keys -t "$SESSION:logs" "tail -f logs/agent.log" Enter

echo "✅ pre-earnings agent started in tmux session '$SESSION'"
echo ""
echo "Commands:"
echo "  tmux attach -t $SESSION          # attach to session"
echo "  tmux kill-session -t $SESSION    # stop everything"
echo "  Ctrl+B then D                    # detach (leave running)"
echo "  Ctrl+B then N                    # next window"
