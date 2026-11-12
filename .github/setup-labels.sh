#!/bin/bash
# Setup GitHub labels for the repository
# Usage: ./setup-labels.sh <owner/repo>

set -e

REPO=${1:-"zerove/ai_developer_growth"}
LABELS_FILE=".github/labels.json"

echo "Setting up labels for $REPO..."

# Check if gh CLI is available
if ! command -v gh &>/dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &>/dev/null; then
    echo "Error: Not authenticated with GitHub CLI."
    echo "Run: gh auth login"
    exit 1
fi

# Read labels from JSON file
if [ ! -f "$LABELS_FILE" ]; then
    echo "Error: Labels file not found: $LABELS_FILE"
    exit 1
fi

# Create labels
echo "Creating labels..."
while IFS= read -r label; do
    name=$(echo "$label" | jq -r '.name')
    description=$(echo "$label" | jq -r '.description')
    color=$(echo "$label" | jq -r '.color')

    echo "  Creating label: $name"
    gh label create "$name" \
        --description "$description" \
        --color "$color" \
        --repo "$REPO" \
        --force 2>/dev/null || echo "    Warning: Failed to create label $name"
done < <(jq -c '.[]' "$LABELS_FILE")

echo "Labels setup complete!"
