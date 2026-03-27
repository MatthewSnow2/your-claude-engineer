#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install click

# Create sample_code directory for testing if it doesn't exist
if [ ! -d "sample_code" ]; then
    mkdir -p sample_code
    cat > sample_code/__init__.py << 'PYEOF'
"""Sample code package for testing csuite."""
PYEOF

    cat > sample_code/module_a.py << 'PYEOF'
"""Module A - Contains sample classes and functions."""
import os
from pathlib import Path


class BaseClass:
    """A base class for demonstration."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        """Return a greeting."""
        return f"Hello, {self.name}"


class SampleClass(BaseClass):
    """A sample class that extends BaseClass."""

    def __init__(self, name: str, value: int = 0):
        super().__init__(name)
        self.value = value

    def compute(self, x: int) -> int:
        """Compute a value."""
        return self.value + x


def func_a(x: int) -> str:
    """Returns a string representation of x."""
    return str(x)


def helper_func(data: list) -> dict:
    """Transforms a list into a dictionary."""
    return {i: v for i, v in enumerate(data)}
PYEOF

    cat > sample_code/module_b.py << 'PYEOF'
"""Module B - Contains more sample classes."""
from .module_a import SampleClass


class AnotherClass:
    """Another class for testing."""

    def __init__(self):
        self.items = []

    def add_item(self, item: str) -> None:
        """Add an item to the list."""
        self.items.append(item)

    def get_items(self) -> list:
        """Return all items."""
        return self.items


class ChildClass(SampleClass):
    """A child class that extends SampleClass."""

    def compute(self, x: int) -> int:
        """Override compute with multiplication."""
        return self.value * x


def func_b(text: str) -> str:
    """Process text by stripping and lowering."""
    return text.strip().lower()
PYEOF

    echo "Created sample_code/ directory with test modules."
fi

echo ""
echo "Setup complete! Activate the virtual environment with:"
echo "  source venv/bin/activate"
echo ""
echo "Then run csuite commands like:"
echo "  python -m csuite parse --path ./sample_code"
echo "  python -m csuite diagram --path ./sample_code --output architecture.mmd"
echo "  python -m csuite docs --path ./sample_code --output docs.md"
