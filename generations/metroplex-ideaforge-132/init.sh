#!/bin/bash
# SkillHub CLI - Development Setup
cd "$(dirname "$0")"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and install dependencies
source venv/bin/activate
pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt 2>/dev/null || pip install click httpx pydantic pytest

echo "SkillHub CLI development environment ready."
echo "Run 'skillhub --help' to get started."
