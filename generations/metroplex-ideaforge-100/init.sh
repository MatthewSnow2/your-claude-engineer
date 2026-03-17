#!/bin/bash
set -e

echo "=== MCP Observability Layer Setup ==="

# Check Python version
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1

# Install package in editable mode
echo "Installing mcp-obs package..."
pip install -e . > /dev/null 2>&1

# Create default database directory
mkdir -p ~/.mcp-obs

echo ""
echo "=== Setup Complete ==="
echo "Run: source venv/bin/activate"
echo "Then: mcp-obs --help"
echo "Or: python -m src.mcp_obs.main --help"
