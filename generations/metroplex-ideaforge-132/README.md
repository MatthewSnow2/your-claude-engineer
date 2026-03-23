# SkillHub CLI

A command-line tool that creates a distributed registry for agent skills based on the Agent Skills open standard. SkillHub enables developers to publish, version, discover, and install reusable agent capabilities as packages, similar to how npm manages JavaScript packages.

## Overview

SkillHub CLI integrates with the Model Context Protocol (MCP) to allow direct skill execution from Claude Code and other compatible agents. It provides a complete ecosystem for managing reusable agent capabilities in a standardized, package-manager-style workflow.

## Tech Stack

- **Python 3.11+** - Core language
- **Click** - Command-line interface framework
- **httpx** - Async HTTP client for API interactions
- **Pydantic** - Data validation and settings management
- **pytest** - Testing framework

## Quick Start

1. Clone or navigate to this repository
2. Run the setup script:
   ```bash
   ./init.sh
   ```
3. Verify installation:
   ```bash
   skillhub --help
   ```

## Features

1. **Publishing** - Publish agent skills as versioned packages to a distributed registry
2. **Discovery & Installation** - Discover available skills and install them with dependency resolution
3. **MCP Execution** - Execute skills directly from Claude Code and other MCP-compatible agents
4. **Validation** - Validate skill definitions against the Agent Skills open standard
5. **Dependency Management** - Manage skill dependencies and version constraints automatically

## Project Structure

```
.
├── README.md           # Project documentation
├── init.sh             # Development environment setup
├── .gitignore          # Git ignore patterns
├── pyproject.toml      # Project metadata and dependencies
├── requirements.txt    # Python dependencies
└── src/
    └── skillhub/       # Main package
```

## Development

After running `init.sh`, activate the virtual environment:
```bash
source venv/bin/activate
```

Run tests:
```bash
pytest
```

## License

MIT
