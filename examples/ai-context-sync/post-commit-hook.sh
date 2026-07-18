#!/bin/bash

# AI-Context-Sync Post-Commit Hook
# This hook triggers the AI synchronization tool after every commit.

# Get the absolute path to the project root
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Path to the AI-Context-Sync main script
# Adjust the path if your installation differs
SYNC_SCRIPT="$PROJECT_ROOT/products/ai-context-sync/src/main.py"

echo "🤖 AI-Context-Sync: Checking for documentation updates..."

# Run the sync tool using python
# Use 'python3' or a specific venv path
python3 -m ai_developer_growth.products.ai_context_sync.src.main

if [ $? -eq 0 ]; then
    echo "✅ AI-Context-Sync completed successfully."
else
    echo "❌ AI-Context-Sync failed. Please check the logs."
fi
