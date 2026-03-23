"""MCP registry client for publishing and discovering skills."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from .models import RegistryEntry, SkillPackage


class RegistryClient:
    """Client for interacting with MCP skill registry."""

    def __init__(
        self,
        registry_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        local_registry_path: Optional[Path] = None,
    ):
        """
        Initialize registry client.

        Args:
            registry_url: Registry API URL
            auth_token: Authentication token
            local_registry_path: Path to local file-based registry (for testing)
        """
        self.registry_url = registry_url or os.getenv(
            "SKILLHUB_REGISTRY_URL", "https://registry.skillhub.dev"
        )
        self.auth_token = auth_token or os.getenv("SKILLHUB_AUTH_TOKEN")
        self.local_registry_path = local_registry_path

        # Use local file-based registry if path provided
        if self.local_registry_path:
            self.local_registry_path.mkdir(parents=True, exist_ok=True)
            self._ensure_registry_index()

    def _ensure_registry_index(self):
        """Ensure local registry index file exists."""
        if self.local_registry_path:
            index_file = self.local_registry_path / "index.json"
            if not index_file.exists():
                index_file.write_text(json.dumps({"skills": {}}, indent=2))

    def _get_headers(self) -> dict:
        """Get HTTP headers for registry requests."""
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def publish_skill(
        self, package: SkillPackage, namespace: Optional[str] = None, private: bool = False
    ) -> RegistryEntry:
        """
        Publish a skill package to the registry.

        Args:
            package: SkillPackage to publish
            namespace: Optional namespace for private skills
            private: Whether skill is private

        Returns:
            RegistryEntry for published skill
        """
        if self.local_registry_path:
            return self._publish_to_local_registry(package, namespace, private)
        else:
            return self._publish_to_remote_registry(package, namespace, private)

    def _publish_to_local_registry(
        self, package: SkillPackage, namespace: Optional[str], private: bool
    ) -> RegistryEntry:
        """Publish to local file-based registry."""
        # Load index
        index_file = self.local_registry_path / "index.json"
        with open(index_file) as f:
            index = json.load(f)

        # Create skill key
        skill_key = f"{namespace}/{package.manifest.name}" if namespace else package.manifest.name

        # Create or update registry entry
        if skill_key in index["skills"]:
            entry_data = index["skills"][skill_key]
            entry = RegistryEntry(**entry_data)
            # Add new version if not exists
            if package.manifest.version not in entry.versions:
                entry.versions.append(package.manifest.version)
                entry.versions.sort(key=lambda v: [int(x) for x in v.split(".")])
                entry.latest_version = entry.versions[-1]
                entry.last_updated = datetime.now(timezone.utc)
        else:
            # Create new entry
            entry = RegistryEntry(
                skill_name=package.manifest.name,
                namespace=namespace,
                versions=[package.manifest.version],
                latest_version=package.manifest.version,
                download_count=0,
                rating=0.0,
                last_updated=datetime.now(timezone.utc),
                mcp_endpoint=f"mcp://registry.skillhub.dev/skills/{skill_key}",
            )

        # Save package files
        skill_dir = self.local_registry_path / skill_key / package.manifest.version
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Save manifest
        manifest_file = skill_dir / "skill.json"
        manifest_file.write_text(package.manifest.model_dump_json(indent=2))

        # Save source files
        for filename, content in package.source_files.items():
            file_path = skill_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(content)

        # Save package metadata
        metadata_file = skill_dir / ".skillpkg-metadata"
        metadata = {
            "package_size": package.package_size,
            "checksum": package.checksum,
            "created_at": package.created_at.isoformat(),
            "namespace": namespace,
            "private": private,
        }
        metadata_file.write_text(json.dumps(metadata, indent=2))

        # Update index
        index["skills"][skill_key] = entry.model_dump(mode="json")
        with open(index_file, "w") as f:
            json.dump(index, f, indent=2, default=str)

        return entry

    def _publish_to_remote_registry(
        self, package: SkillPackage, namespace: Optional[str], private: bool
    ) -> RegistryEntry:
        """Publish to remote HTTP registry."""
        # Prepare publish request
        publish_data = {
            "manifest": package.manifest.model_dump(),
            "checksum": package.checksum,
            "package_size": package.package_size,
            "namespace": namespace,
            "private": private,
        }

        # Make publish request
        with httpx.Client() as client:
            response = client.post(
                f"{self.registry_url}/api/v1/skills/publish",
                json=publish_data,
                headers=self._get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()

            # Parse response
            entry_data = response.json()
            return RegistryEntry(**entry_data)

    def get_skill(self, skill_name: str, namespace: Optional[str] = None) -> Optional[RegistryEntry]:
        """
        Get skill information from registry.

        Args:
            skill_name: Skill name
            namespace: Optional namespace

        Returns:
            RegistryEntry or None if not found
        """
        if self.local_registry_path:
            return self._get_from_local_registry(skill_name, namespace)
        else:
            return self._get_from_remote_registry(skill_name, namespace)

    def _get_from_local_registry(
        self, skill_name: str, namespace: Optional[str]
    ) -> Optional[RegistryEntry]:
        """Get skill from local registry."""
        index_file = self.local_registry_path / "index.json"
        with open(index_file) as f:
            index = json.load(f)

        skill_key = f"{namespace}/{skill_name}" if namespace else skill_name

        if skill_key in index["skills"]:
            return RegistryEntry(**index["skills"][skill_key])

        return None

    def _get_from_remote_registry(
        self, skill_name: str, namespace: Optional[str]
    ) -> Optional[RegistryEntry]:
        """Get skill from remote registry."""
        params = {"name": skill_name}
        if namespace:
            params["namespace"] = namespace

        with httpx.Client() as client:
            response = client.get(
                f"{self.registry_url}/api/v1/skills",
                params=params,
                headers=self._get_headers(),
                timeout=10.0,
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            return RegistryEntry(**response.json())

    def check_skill_exists(self, skill_name: str, version: str, namespace: Optional[str] = None) -> bool:
        """
        Check if a specific skill version exists in registry.

        Args:
            skill_name: Skill name
            version: Version to check
            namespace: Optional namespace

        Returns:
            True if exists, False otherwise
        """
        entry = self.get_skill(skill_name, namespace)
        if not entry:
            return False

        return version in entry.versions
