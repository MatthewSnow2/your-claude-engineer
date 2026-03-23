"""MCP registry client for publishing and discovering skills."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx

from .models import RegistryEntry, SkillManifest, SkillPackage


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
                def _version_key(v):
                    try:
                        return [int(x) for x in v.split(".")]
                    except (ValueError, AttributeError):
                        return [0, 0, 0]
                entry.versions.sort(key=_version_key)
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

    def search_skills(
        self, query: Optional[str] = None, tags: Optional[List[str]] = None, limit: int = 10
    ) -> List[RegistryEntry]:
        """
        Search for skills in the registry.

        Args:
            query: Search query to match against skill name and description
            tags: List of tags to filter by
            limit: Maximum number of results to return

        Returns:
            List of matching RegistryEntry objects
        """
        if self.local_registry_path:
            return self._search_local_registry(query, tags, limit)
        else:
            return self._search_remote_registry(query, tags, limit)

    def _search_local_registry(
        self, query: Optional[str], tags: Optional[List[str]], limit: int
    ) -> List[RegistryEntry]:
        """Search local file-based registry."""
        index_file = self.local_registry_path / "index.json"
        with open(index_file) as f:
            index = json.load(f)

        results = []

        for skill_key, entry_data in index["skills"].items():
            entry = RegistryEntry(**entry_data)

            # Load manifest to check keywords
            skill_dir = self.local_registry_path / skill_key / entry.latest_version
            manifest_path = skill_dir / "skill.json"

            if manifest_path.exists():
                with open(manifest_path) as f:
                    manifest_data = json.load(f)
                    manifest = SkillManifest(**manifest_data)

                # Check if query matches
                if query:
                    query_lower = query.lower()
                    # Match against name, description, and keywords
                    if not (
                        query_lower in entry.skill_name.lower()
                        or query_lower in manifest.description.lower()
                        or any(query_lower in kw.lower() for kw in manifest.keywords)
                    ):
                        continue

                # Check if tags match
                if tags:
                    if not any(tag in manifest.keywords for tag in tags):
                        continue

            results.append(entry)

            if len(results) >= limit:
                break

        # Sort by rating and download count
        results.sort(key=lambda e: (e.rating, e.download_count), reverse=True)

        return results

    def _search_remote_registry(
        self, query: Optional[str], tags: Optional[List[str]], limit: int
    ) -> List[RegistryEntry]:
        """Search remote HTTP registry."""
        params = {"limit": limit}
        if query:
            params["q"] = query
        if tags:
            params["tags"] = ",".join(tags)

        with httpx.Client() as client:
            response = client.get(
                f"{self.registry_url}/api/v1/skills/search",
                params=params,
                headers=self._get_headers(),
                timeout=10.0,
            )
            response.raise_for_status()

            results_data = response.json()
            return [RegistryEntry(**entry) for entry in results_data.get("skills", [])]

    def download_skill_package(
        self, skill_name: str, version: str, namespace: Optional[str] = None
    ) -> Optional[SkillPackage]:
        """
        Download a skill package from the registry.

        Args:
            skill_name: Skill name
            version: Skill version
            namespace: Optional namespace

        Returns:
            SkillPackage or None if not found
        """
        if self.local_registry_path:
            return self._download_from_local_registry(skill_name, version, namespace)
        else:
            return self._download_from_remote_registry(skill_name, version, namespace)

    def _download_from_local_registry(
        self, skill_name: str, version: str, namespace: Optional[str]
    ) -> Optional[SkillPackage]:
        """Download from local registry."""
        skill_key = f"{namespace}/{skill_name}" if namespace else skill_name
        skill_dir = self.local_registry_path / skill_key / version

        if not skill_dir.exists():
            return None

        # Load manifest
        manifest_path = skill_dir / "skill.json"
        if not manifest_path.exists():
            return None

        with open(manifest_path) as f:
            manifest_data = json.load(f)
        manifest = SkillManifest(**manifest_data)

        # Collect all source files
        source_files = {}
        for file_path in skill_dir.rglob("*"):
            if file_path.is_file() and not file_path.is_symlink() and file_path.name != ".skillpkg-metadata":
                rel_path = file_path.relative_to(skill_dir)
                source_files[str(rel_path)] = file_path.read_bytes()

        # Load metadata
        metadata_path = skill_dir / ".skillpkg-metadata"
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)
        else:
            metadata = {
                "package_size": sum(len(c) for c in source_files.values()),
                "checksum": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        # Create package
        package = SkillPackage(
            manifest=manifest,
            source_files=source_files,
            package_size=metadata.get("package_size", 0),
            checksum=metadata.get("checksum", ""),
            created_at=datetime.fromisoformat(
                metadata.get("created_at", datetime.now(timezone.utc).isoformat())
            ),
        )

        return package

    def _download_from_remote_registry(
        self, skill_name: str, version: str, namespace: Optional[str]
    ) -> Optional[SkillPackage]:
        """Download from remote registry."""
        params = {"version": version}
        if namespace:
            params["namespace"] = namespace

        with httpx.Client() as client:
            response = client.get(
                f"{self.registry_url}/api/v1/skills/{skill_name}/download",
                params=params,
                headers=self._get_headers(),
                timeout=30.0,
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            package_data = response.json()
            return SkillPackage(**package_data)
