# Codebase Understanding Suite (csuite)

A command-line utility that scans a local Python codebase, extracts its structural elements (modules, classes, functions, and relationships), and produces two artifacts:
- A **Mermaid diagram** that visualizes the code's architecture
- A **Markdown document** that provides readable documentation

## Tech Stack
- Python 3.11+
- `click` (for CLI)
- Standard library (`ast`, `dataclasses`, `json`, `pathlib`, `textwrap`)

## Usage

```bash
# Parse a codebase
python -m csuite parse --path ./your_code

# Generate Mermaid diagram
python -m csuite diagram --path ./your_code --output architecture.mmd

# Generate Markdown docs
python -m csuite docs --path ./your_code --output docs.md
```

## Setup

```bash
chmod +x init.sh
./init.sh
```

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `CSUITE_OUTPUT_DIR` | `.` | Directory where generated files are written |
