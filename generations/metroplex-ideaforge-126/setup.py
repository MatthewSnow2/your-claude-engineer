"""Setup configuration for VoiceNotify MCP Plugin."""

from setuptools import setup, find_packages

setup(
    name="voicenotify",
    version="0.1.0",
    description="MCP Plugin for agent event notifications",
    author="VoiceNotify Team",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[],
    extras_require={
        "dev": ["pytest", "pytest-cov"],
    },
    entry_points={
        "console_scripts": [
            "voicenotify=voicenotify.main:main",
        ],
    },
)
