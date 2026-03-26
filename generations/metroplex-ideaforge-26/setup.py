"""Setup configuration for CommitNarrative."""

from pathlib import Path
from setuptools import setup, find_packages

# Read the README file
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

setup(
    name="commitnarrative",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "commitnarrative=commitnarrative.cli:cli",
        ],
    },
    python_requires=">=3.11",
    author="CommitNarrative Team",
    description="Transform Git commits into social media updates",
    long_description=long_description,
    long_description_content_type="text/markdown",
)
