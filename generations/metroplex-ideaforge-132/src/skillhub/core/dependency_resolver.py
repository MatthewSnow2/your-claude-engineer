"""Dependency resolution for agent skills with semantic versioning."""

import re
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from .cache import SkillCacheManager
from .models import SkillManifest
from .registry import RegistryClient


class ResolvedDependency(BaseModel):
    """A resolved dependency with version information."""

    name: str = Field(..., description="Skill name")
    version: str = Field(..., description="Resolved version")
    constraint: str = Field(..., description="Original version constraint")
    dependencies: Dict[str, str] = Field(default_factory=dict, description="Sub-dependencies")
    is_dev: bool = Field(default=False, description="Is development dependency")


class ConflictInfo(BaseModel):
    """Information about a version conflict."""

    skill_name: str = Field(..., description="Skill with conflict")
    required_by: Dict[str, str] = Field(..., description="Map of requester to constraint")
    available_versions: List[str] = Field(..., description="Available versions")
    resolved_version: Optional[str] = Field(default=None, description="Resolved version if any")


class ResolvedDependencies(BaseModel):
    """Complete resolution of all dependencies."""

    dependencies: List[ResolvedDependency] = Field(..., description="All resolved dependencies")
    conflicts: List[ConflictInfo] = Field(default_factory=list, description="Detected conflicts")
    resolution_order: List[str] = Field(..., description="Installation order")


class DependencyResolver:
    """Resolves skill dependencies using semantic versioning."""

    def __init__(self, registry: RegistryClient, cache: SkillCacheManager):
        """
        Initialize dependency resolver.

        Args:
            registry: Registry client for fetching skill info
            cache: Cache manager for installed skills
        """
        self.registry = registry
        self.cache = cache

    def parse_version_constraint(self, constraint: str) -> Tuple[str, str]:
        """
        Parse a semantic version constraint.

        Args:
            constraint: Version constraint like '^1.2.0', '~1.2.0', '>=1.0.0,<2.0.0', '*', or exact

        Returns:
            Tuple of (operator, version) where operator is one of: 'exact', 'caret', 'tilde', 'range', 'any'
        """
        constraint = constraint.strip()

        # Wildcard
        if constraint == "*" or constraint == "latest":
            return ("any", "")

        # Caret (^1.2.3 - compatible with 1.x.x)
        if constraint.startswith("^"):
            return ("caret", constraint[1:])

        # Tilde (~1.2.3 - compatible with 1.2.x)
        if constraint.startswith("~"):
            return ("tilde", constraint[1:])

        # Range (>=1.0.0,<2.0.0)
        if ">=" in constraint or "<=" in constraint or ">" in constraint or "<" in constraint:
            return ("range", constraint)

        # Exact version
        return ("exact", constraint)

    def version_satisfies(self, version: str, constraint: str) -> bool:
        """
        Check if a version satisfies a constraint.

        Args:
            version: Version to check (e.g., '1.2.3')
            constraint: Version constraint

        Returns:
            True if version satisfies constraint
        """
        operator, constraint_version = self.parse_version_constraint(constraint)

        if operator == "any":
            return True

        if operator == "exact":
            return version == constraint_version

        if operator == "range":
            # Parse range constraints like ">=1.0.0,<2.0.0"
            parts = constraint_version.split(",")
            for part in parts:
                part = part.strip()
                if part.startswith(">="):
                    min_version = part[2:].strip()
                    if self.compare_versions(version, min_version) < 0:
                        return False
                elif part.startswith("<="):
                    max_version = part[2:].strip()
                    if self.compare_versions(version, max_version) > 0:
                        return False
                elif part.startswith(">"):
                    min_version = part[1:].strip()
                    if self.compare_versions(version, min_version) <= 0:
                        return False
                elif part.startswith("<"):
                    max_version = part[1:].strip()
                    if self.compare_versions(version, max_version) >= 0:
                        return False
            return True

        # Parse version numbers for caret and tilde
        try:
            v_parts = [int(x) for x in version.split(".")]
            c_parts = [int(x) for x in constraint_version.split(".")]
        except (ValueError, AttributeError):
            return False

        # Ensure 3 parts
        while len(v_parts) < 3:
            v_parts.append(0)
        while len(c_parts) < 3:
            c_parts.append(0)

        if operator == "caret":
            # ^1.2.3 means >=1.2.3 and <2.0.0
            # ^0.2.3 means >=0.2.3 and <0.3.0
            # ^0.0.3 means >=0.0.3 and <0.0.4
            if c_parts[0] > 0:
                return v_parts[0] == c_parts[0] and (v_parts[1] > c_parts[1] or
                       (v_parts[1] == c_parts[1] and v_parts[2] >= c_parts[2]))
            elif c_parts[1] > 0:
                return v_parts[0] == 0 and v_parts[1] == c_parts[1] and v_parts[2] >= c_parts[2]
            else:
                return v_parts[0] == 0 and v_parts[1] == 0 and v_parts[2] == c_parts[2]

        if operator == "tilde":
            # ~1.2.3 means >=1.2.3 and <1.3.0
            return (v_parts[0] == c_parts[0] and v_parts[1] == c_parts[1] and
                   v_parts[2] >= c_parts[2])

        return False

    def compare_versions(self, v1: str, v2: str) -> int:
        """
        Compare two semantic versions.

        Args:
            v1: First version
            v2: Second version

        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
        """
        try:
            v1_parts = [int(x) for x in v1.split(".")]
            v2_parts = [int(x) for x in v2.split(".")]
        except (ValueError, AttributeError):
            # Fall back to string comparison
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
            else:
                return 0

        # Ensure 3 parts
        while len(v1_parts) < 3:
            v1_parts.append(0)
        while len(v2_parts) < 3:
            v2_parts.append(0)

        for i in range(3):
            if v1_parts[i] < v2_parts[i]:
                return -1
            elif v1_parts[i] > v2_parts[i]:
                return 1

        return 0

    def find_best_version(self, available_versions: List[str], constraint: str) -> Optional[str]:
        """
        Find the best matching version for a constraint.

        Args:
            available_versions: List of available versions
            constraint: Version constraint

        Returns:
            Best matching version or None
        """
        matching = [v for v in available_versions if self.version_satisfies(v, constraint)]

        if not matching:
            return None

        # Return the highest matching version
        matching.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
        return matching[0]

    def resolve_dependencies(
        self,
        manifest: SkillManifest,
        include_dev: bool = False,
        namespace: Optional[str] = None
    ) -> ResolvedDependencies:
        """
        Resolve all dependencies for a skill manifest.

        Args:
            manifest: Skill manifest to resolve dependencies for
            include_dev: Whether to include dev dependencies
            namespace: Optional namespace for skills

        Returns:
            ResolvedDependencies with all resolved deps and conflicts
        """
        resolved: Dict[str, ResolvedDependency] = {}
        conflicts: List[ConflictInfo] = []
        requirements: Dict[str, Dict[str, str]] = {}  # skill_name -> {requester: constraint}

        # Start with direct dependencies
        to_resolve: List[Tuple[str, str, str, bool]] = []  # (name, constraint, requester, is_dev)

        for dep_name, dep_constraint in manifest.dependencies.items():
            to_resolve.append((dep_name, dep_constraint, manifest.name, False))
            requirements[dep_name] = {manifest.name: dep_constraint}

        if include_dev:
            for dep_name, dep_constraint in manifest.dev_dependencies.items():
                to_resolve.append((dep_name, dep_constraint, manifest.name, True))
                if dep_name not in requirements:
                    requirements[dep_name] = {}
                requirements[dep_name][manifest.name] = dep_constraint

        visited: Set[str] = set()

        while to_resolve:
            dep_name, dep_constraint, requester, is_dev = to_resolve.pop(0)

            # Skip if already resolved with compatible version
            if dep_name in resolved:
                # Check if existing resolution satisfies this constraint
                if self.version_satisfies(resolved[dep_name].version, dep_constraint):
                    continue
                else:
                    # Conflict detected
                    if dep_name not in requirements:
                        requirements[dep_name] = {}
                    requirements[dep_name][requester] = dep_constraint

            # Check cache first
            cached = self.cache.get_cached_skill(dep_name)
            if cached and self.version_satisfies(cached.version, dep_constraint):
                dep_version = cached.version
                dep_manifest = cached.manifest
            else:
                # Fetch from registry
                try:
                    entry = self.registry.get_skill(dep_name, namespace)
                    if not entry:
                        # Skill not found
                        conflicts.append(ConflictInfo(
                            skill_name=dep_name,
                            required_by={requester: dep_constraint},
                            available_versions=[],
                            resolved_version=None
                        ))
                        continue

                    # Find best matching version
                    best_version = self.find_best_version(entry.versions, dep_constraint)
                    if not best_version:
                        # No matching version
                        conflicts.append(ConflictInfo(
                            skill_name=dep_name,
                            required_by={requester: dep_constraint},
                            available_versions=entry.versions,
                            resolved_version=None
                        ))
                        continue

                    dep_version = best_version

                    # Download to get manifest
                    package = self.registry.download_skill_package(dep_name, dep_version, namespace)
                    if not package:
                        conflicts.append(ConflictInfo(
                            skill_name=dep_name,
                            required_by={requester: dep_constraint},
                            available_versions=entry.versions,
                            resolved_version=None
                        ))
                        continue

                    dep_manifest = package.manifest

                except (ValueError, OSError):
                    # Error fetching skill
                    conflicts.append(ConflictInfo(
                        skill_name=dep_name,
                        required_by={requester: dep_constraint},
                        available_versions=[],
                        resolved_version=None
                    ))
                    continue

            # Check if this version satisfies all requirements
            if dep_name in requirements:
                all_satisfied = True
                for req_constraint in requirements[dep_name].values():
                    if not self.version_satisfies(dep_version, req_constraint):
                        all_satisfied = False
                        break

                if not all_satisfied:
                    # Try to find a version that satisfies all
                    try:
                        entry = self.registry.get_skill(dep_name, namespace)
                        if entry:
                            # Find version satisfying all constraints
                            for version in sorted(entry.versions,
                                                key=lambda v: [int(x) for x in v.split(".")],
                                                reverse=True):
                                satisfies_all = True
                                for req_constraint in requirements[dep_name].values():
                                    if not self.version_satisfies(version, req_constraint):
                                        satisfies_all = False
                                        break

                                if satisfies_all:
                                    dep_version = version
                                    all_satisfied = True
                                    break
                    except (ValueError, OSError):
                        pass

                if not all_satisfied:
                    conflicts.append(ConflictInfo(
                        skill_name=dep_name,
                        required_by=requirements[dep_name],
                        available_versions=entry.versions if entry else [],
                        resolved_version=dep_version
                    ))

            # Add to resolved
            resolved[dep_name] = ResolvedDependency(
                name=dep_name,
                version=dep_version,
                constraint=dep_constraint,
                dependencies=dep_manifest.dependencies,
                is_dev=is_dev
            )

            # Add sub-dependencies to queue
            dep_key = f"{dep_name}@{dep_version}"
            if dep_key not in visited:
                visited.add(dep_key)
                for sub_dep_name, sub_dep_constraint in dep_manifest.dependencies.items():
                    to_resolve.append((sub_dep_name, sub_dep_constraint, dep_name, is_dev))
                    if sub_dep_name not in requirements:
                        requirements[sub_dep_name] = {}
                    requirements[sub_dep_name][dep_name] = sub_dep_constraint

        # Build resolution order (topological sort)
        resolution_order = self._build_resolution_order(resolved)

        return ResolvedDependencies(
            dependencies=list(resolved.values()),
            conflicts=conflicts,
            resolution_order=resolution_order
        )

    def _build_resolution_order(self, resolved: Dict[str, ResolvedDependency]) -> List[str]:
        """
        Build installation order using topological sort.

        Args:
            resolved: Dict of resolved dependencies

        Returns:
            List of skill names in installation order
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}

        for dep in resolved.values():
            graph[dep.name] = set()
            in_degree[dep.name] = 0

        for dep in resolved.values():
            for sub_dep in dep.dependencies:
                if sub_dep in resolved:
                    graph[sub_dep].add(dep.name)
                    in_degree[dep.name] += 1

        # Topological sort (Kahn's algorithm)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            current = queue.pop(0)
            order.append(current)

            for dependent in graph[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(order) != len(resolved):
            # Circular dependency - return partial order
            remaining = [name for name in resolved if name not in order]
            order.extend(sorted(remaining))

        return order

    def detect_conflicts(self, resolved: ResolvedDependencies) -> List[ConflictInfo]:
        """
        Detect version conflicts in resolved dependencies.

        Args:
            resolved: Resolved dependencies

        Returns:
            List of conflict information
        """
        return resolved.conflicts

    def generate_lock_data(self, resolved: ResolvedDependencies) -> dict:
        """
        Generate lock file data from resolved dependencies.

        Args:
            resolved: Resolved dependencies

        Returns:
            Lock file data as dict
        """
        from datetime import datetime, timezone

        lock_data = {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dependencies": {},
            "resolution_order": resolved.resolution_order
        }

        for dep in resolved.dependencies:
            lock_data["dependencies"][dep.name] = {
                "version": dep.version,
                "constraint": dep.constraint,
                "dependencies": dep.dependencies,
                "is_dev": dep.is_dev
            }

        return lock_data
