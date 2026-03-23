"""Data models for SkillHub CLI."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow():
    """Return current UTC time."""
    return datetime.now(timezone.utc)


class SkillCapability(BaseModel):
    """Represents a skill capability."""

    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    input_schema: Dict[str, Any] = Field(..., description="JSON schema for inputs")
    output_schema: Dict[str, Any] = Field(..., description="JSON schema for outputs")
    required_permissions: List[str] = Field(
        default_factory=list, description="Required permissions"
    )


class MCPToolDefinition(BaseModel):
    """MCP tool definition for skill integration."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputSchema: Dict[str, Any] = Field(..., description="JSON schema for tool inputs")
    function_path: str = Field(..., description="Python path to function")


class AgentCompatibility(BaseModel):
    """Agent compatibility information."""

    claude_code: bool = Field(default=True, description="Compatible with Claude Code")
    custom_agents: List[str] = Field(
        default_factory=list, description="List of custom agent names"
    )
    runtime_requirements: List[str] = Field(
        default_factory=list, description="Runtime requirements"
    )


class SkillManifest(BaseModel):
    """Skill manifest (skill.json) model."""

    name: str = Field(..., description="Skill name")
    version: str = Field(..., description="Semantic version")
    description: str = Field(..., description="Skill description")
    author: str = Field(..., description="Author name")
    agent_skills_version: str = Field(
        default="1.0.0", description="Agent Skills standard version"
    )
    capabilities: List[SkillCapability] = Field(..., description="Skill capabilities")
    dependencies: Dict[str, str] = Field(
        default_factory=dict, description="Runtime dependencies"
    )
    dev_dependencies: Dict[str, str] = Field(
        default_factory=dict, description="Development dependencies"
    )
    main_module: str = Field(..., description="Main module path")
    mcp_tools: List[MCPToolDefinition] = Field(
        default_factory=list, description="MCP tool definitions"
    )
    compatibility: AgentCompatibility = Field(
        default_factory=AgentCompatibility, description="Agent compatibility"
    )
    license: str = Field(..., description="License identifier")
    keywords: List[str] = Field(default_factory=list, description="Searchable keywords")
    repository: Optional[str] = Field(default=None, description="Repository URL")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must be in format X.Y.Z")
        for part in parts:
            if not part.isdigit():
                raise ValueError("Version parts must be numeric")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate skill name format."""
        if not v:
            raise ValueError("Skill name cannot be empty")
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Skill name must contain only alphanumeric, dash, or underscore")
        return v


class SkillPackage(BaseModel):
    """Packaged skill bundle."""

    manifest: SkillManifest = Field(..., description="Skill manifest")
    source_files: Dict[str, bytes] = Field(..., description="Source files with content")
    package_size: int = Field(..., description="Package size in bytes")
    checksum: str = Field(..., description="SHA256 checksum")
    created_at: datetime = Field(
        default_factory=_utcnow, description="Package creation timestamp"
    )


class RegistryEntry(BaseModel):
    """Registry entry for published skill."""

    skill_name: str = Field(..., description="Skill name")
    namespace: Optional[str] = Field(default=None, description="Optional namespace")
    versions: List[str] = Field(..., description="Available versions")
    latest_version: str = Field(..., description="Latest version")
    download_count: int = Field(default=0, description="Total downloads")
    rating: float = Field(default=0.0, description="Average rating")
    last_updated: datetime = Field(
        default_factory=_utcnow, description="Last update timestamp"
    )
    mcp_endpoint: str = Field(..., description="MCP endpoint URL")


class LocalSkillCache(BaseModel):
    """Local skill cache metadata."""

    installed_skills: Dict[str, SkillPackage] = Field(
        default_factory=dict, description="Installed skill packages"
    )
    dependency_graph: Dict[str, List[str]] = Field(
        default_factory=dict, description="Dependency relationships"
    )
    cache_version: str = Field(default="1.0.0", description="Cache format version")
    last_sync: datetime = Field(
        default_factory=_utcnow, description="Last sync timestamp"
    )
