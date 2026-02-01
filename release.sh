#!/bin/bash
# Release script for ai-screenshooter
# Usage: ./release.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load token from .pypi-token file
TOKEN_FILE="$SCRIPT_DIR/.pypi-token"
if [[ ! -f "$TOKEN_FILE" ]]; then
    echo -e "${RED}Error: .pypi-token file not found${NC}"
    echo "Create it with: echo 'pypi-YOUR_TOKEN' > .pypi-token"
    exit 1
fi
PYPI_TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')

# Get current version from setup.py
CURRENT_VERSION=$(grep -E '^\s*version=' setup.py | sed 's/.*version="\([^"]*\)".*/\1/')
echo -e "${YELLOW}Current version: ${GREEN}$CURRENT_VERSION${NC}"

# Ask for new version
read -p "Enter new version (or press Enter to keep $CURRENT_VERSION): " NEW_VERSION

if [[ -z "$NEW_VERSION" ]]; then
    NEW_VERSION="$CURRENT_VERSION"
fi

# Validate version format (simple check)
if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Version must be in format X.Y.Z (e.g., 1.2.3)${NC}"
    exit 1
fi

echo -e "${YELLOW}Releasing version: ${GREEN}$NEW_VERSION${NC}"
echo ""

# Update version in setup.py
if [[ "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
    echo "Updating setup.py..."
    sed -i '' "s/version=\"$CURRENT_VERSION\"/version=\"$NEW_VERSION\"/" setup.py
fi

# Activate virtual environment if exists
if [[ -d ".venv" ]]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install/upgrade build tools
echo "Checking build tools..."
pip install --quiet --upgrade build twine

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info

# Build
echo "Building package..."
python -m build

# Show what will be uploaded
echo ""
echo -e "${YELLOW}Files to upload:${NC}"
ls -la dist/

echo ""
read -p "Upload to PyPI? (y/N): " CONFIRM

if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Uploading to PyPI..."
    twine upload dist/* -u __token__ -p "$PYPI_TOKEN"

    echo ""
    echo -e "${GREEN}Successfully released version $NEW_VERSION!${NC}"
    echo ""
    echo "Install with: pipx install ai-screenshooter==$NEW_VERSION"
    echo "Upgrade with: pipx upgrade ai-screenshooter"

    # Commit version bump if changed
    if [[ "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
        read -p "Commit and push version bump? (y/N): " COMMIT_CONFIRM
        if [[ "$COMMIT_CONFIRM" =~ ^[Yy]$ ]]; then
            git add setup.py
            git commit -m "Bump version to $NEW_VERSION"
            git push
            echo -e "${GREEN}Version bump committed and pushed${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Upload cancelled${NC}"
    # Revert version if changed
    if [[ "$NEW_VERSION" != "$CURRENT_VERSION" ]]; then
        sed -i '' "s/version=\"$NEW_VERSION\"/version=\"$CURRENT_VERSION\"/" setup.py
        echo "Reverted version to $CURRENT_VERSION"
    fi
fi
