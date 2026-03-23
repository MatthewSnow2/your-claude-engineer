"""Local skill cache management."""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import SkillManifest, SkillPackage
from .packaging import MAX_FILE_SIZE, MAX_PACKAGE_SIZE


class CachedSkillInfo:
    """Information about a cached skill."""

    def __init__(self, name: str, version: str, manifest: SkillManifest, install_path: Path):
        """Initialize cached skill info."""
        self.name = name
        self.version = version
        self.manifest = manifest
        self.install_path = install_path


class SkillCacheManager:
    """Manages local skill cache for offline access."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Custom cache directory (defaults to ~/.skillhub)
        """
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            cache_dir_str = os.getenv("SKILLHUB_CACHE_DIR")
            if cache_dir_str:
                self.cache_dir = Path(cache_dir_str)
            else:
                self.cache_dir = Path.home() / ".skillhub"

        self.cache_dir = self.cache_dir.resolve()
        self.skills_dir = self.cache_dir / "cache" / "skills"
        self.index_file = self.cache_dir / "cache" / "cache_index.json"

        # Ensure directories exist
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    def _ensure_index(self):
        """Ensure cache index file exists."""
        if not self.index_file.exists():
            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            index_data = {
                "cache_version": "1.0.0",
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "installed_skills": {},
                "dependency_graph": {},
            }
            self.index_file.write_text(json.dumps(index_data, indent=2))

    def _load_index(self) -> dict:
        """Load cache index from file."""
        with open(self.index_file) as f:
            return json.load(f)

    def _save_index(self, index: dict):
        """Save cache index to file."""
        index["last_sync"] = datetime.now(timezone.utc).isoformat()
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)

    def get_cache_dir(self) -> Path:
        """
        Get the cache directory path.

        Returns:
            Path to cache directory
        """
        return self.cache_dir

    def cache_skill(
        self, skill_name: str, version: str, manifest: SkillManifest, files: Dict[str, bytes]
    ) -> Path:
        """
        Cache a skill package locally.

        Args:
            skill_name: Skill name
            version: Skill version
            manifest: Skill manifest
            files: Dictionary of file paths to content

        Returns:
            Path to cached skill directory
        """
        # Validate total package size
        total_size = sum(len(content) for content in files.values())
        if total_size > MAX_PACKAGE_SIZE:
            raise ValueError(f"Package too large: {total_size} bytes (max {MAX_PACKAGE_SIZE})")

        # Create skill version directory
        skill_version_dir = self.skills_dir / skill_name / version
        skill_version_dir.mkdir(parents=True, exist_ok=True)

        # Write all files with path traversal and size validation
        for file_path, content in files.items():
            # Validate file size
            if len(content) > MAX_FILE_SIZE:
                raise ValueError(f"File too large: {file_path} ({len(content)} bytes, max {MAX_FILE_SIZE})")

            target_path = (skill_version_dir / file_path).resolve()
            # Validate path is within skill_version_dir
            if not target_path.is_relative_to(skill_version_dir.resolve()):
                raise ValueError(f"Path traversal attempt detected: {file_path}")
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)

        # Update index
        index = self._load_index()
        if skill_name not in index["installed_skills"]:
            index["installed_skills"][skill_name] = {
                "versions": [],
                "latest_version": version,
            }

        skill_info = index["installed_skills"][skill_name]
        if version not in skill_info["versions"]:
            skill_info["versions"].append(version)
            def _version_key(v):
                try:
                    return [int(x) for x in v.split(".")]
                except (ValueError, AttributeError):
                    return [0, 0, 0]
            skill_info["versions"].sort(key=_version_key)

        # Update latest version
        skill_info["latest_version"] = skill_info["versions"][-1]

        # Add metadata
        skill_info["install_path"] = str(skill_version_dir)
        skill_info["installed_at"] = datetime.now(timezone.utc).isoformat()

        # Store dependency info
        if manifest.dependencies:
            index["dependency_graph"][f"{skill_name}@{version}"] = list(
                manifest.dependencies.keys()
            )

        self._save_index(index)
        return skill_version_dir

    def get_cached_skill(
        self, skill_name: str, version: Optional[str] = None
    ) -> Optional[CachedSkillInfo]:
        """
        Get cached skill information.

        Args:
            skill_name: Skill name
            version: Specific version (or latest if None)

        Returns:
            CachedSkillInfo or None if not found
        """
        index = self._load_index()

        if skill_name not in index["installed_skills"]:
            return None

        skill_info = index["installed_skills"][skill_name]

        # Determine version to use
        if version is None:
            version = skill_info["latest_version"]
        elif version not in skill_info["versions"]:
            return None

        # Load manifest
        skill_dir = self.skills_dir / skill_name / version
        manifest_path = skill_dir / "skill.json"

        if not manifest_path.exists():
            return None

        with open(manifest_path) as f:
            manifest_data = json.load(f)

        manifest = SkillManifest(**manifest_data)

        return CachedSkillInfo(
            name=skill_name, version=version, manifest=manifest, install_path=skill_dir
        )

    def list_installed(self) -> List[CachedSkillInfo]:
        """
        List all installed skills.

        Returns:
            List of CachedSkillInfo objects
        """
        index = self._load_index()
        installed = []

        for skill_name, skill_info in index["installed_skills"].items():
            latest_version = skill_info["latest_version"]
            cached_skill = self.get_cached_skill(skill_name, latest_version)
            if cached_skill:
                installed.append(cached_skill)

        return installed

    def remove_skill(self, skill_name: str, version: Optional[str] = None) -> bool:
        """
        Remove a skill from cache.

        Args:
            skill_name: Skill name
            version: Specific version to remove (or all versions if None)

        Returns:
            True if removed, False if not found
        """
        index = self._load_index()

        if skill_name not in index["installed_skills"]:
            return False

        skill_info = index["installed_skills"][skill_name]

        if version is None:
            # Remove all versions
            skill_dir = self.skills_dir / skill_name
            if skill_dir.exists():
                shutil.rmtree(skill_dir)

            del index["installed_skills"][skill_name]

            # Remove from dependency graph
            deps_to_remove = [k for k in index["dependency_graph"] if k.startswith(f"{skill_name}@")]
            for dep_key in deps_to_remove:
                del index["dependency_graph"][dep_key]

        else:
            # Remove specific version
            if version not in skill_info["versions"]:
                return False

            version_dir = self.skills_dir / skill_name / version
            if version_dir.exists():
                shutil.rmtree(version_dir)

            skill_info["versions"].remove(version)

            if not skill_info["versions"]:
                # No versions left, remove skill entirely
                skill_dir = self.skills_dir / skill_name
                if skill_dir.exists():
                    shutil.rmtree(skill_dir)
                del index["installed_skills"][skill_name]
            else:
                # Update latest version
                skill_info["latest_version"] = skill_info["versions"][-1]

            # Remove from dependency graph
            dep_key = f"{skill_name}@{version}"
            if dep_key in index["dependency_graph"]:
                del index["dependency_graph"][dep_key]

        self._save_index(index)
        return True

    def skill_exists(self, skill_name: str, version: Optional[str] = None) -> bool:
        """
        Check if a skill exists in cache.

        Args:
            skill_name: Skill name
            version: Specific version (or any version if None)

        Returns:
            True if exists, False otherwise
        """
        cached = self.get_cached_skill(skill_name, version)
        return cached is not None
