import json
import os
from pathlib import Path
from typing import List

from llm_citation_checker.models import Fact


def load_kb() -> List[Fact]:
    """
    Load knowledge base from kb.json file.

    Tries to find the file in the following order:
    1. Environment variable LCC_KB_PATH if set
    2. data/kb.json relative to the package directory
    3. data/kb.json relative to the current working directory

    Returns:
        List[Fact]: List of facts loaded from the knowledge base
    """
    # Check environment variable first
    kb_path_env = os.getenv("LCC_KB_PATH")
    if kb_path_env and os.path.exists(kb_path_env):
        kb_path = Path(kb_path_env)
    else:
        # Try to find relative to package directory
        package_dir = Path(__file__).parent.parent
        kb_path = package_dir / "data" / "kb.json"

        # Fall back to current working directory
        if not kb_path.exists():
            kb_path = Path.cwd() / "data" / "kb.json"

    if not kb_path.exists():
        raise FileNotFoundError(
            f"Knowledge base file not found. Tried: {kb_path}\n"
            "Set LCC_KB_PATH environment variable or ensure data/kb.json exists."
        )

    with open(kb_path, "r") as f:
        data = json.load(f)

    return [Fact(**item) for item in data]
