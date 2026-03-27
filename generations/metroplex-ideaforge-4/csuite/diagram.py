"""Mermaid diagram generation for Feature 2."""
from typing import List, Dict, Set
from .models import ModuleSymbol, ClassSymbol, FunctionSymbol


def generate_mermaid_diagram(modules: List[ModuleSymbol]) -> str:
    """
    Generate a Mermaid class diagram from parsed modules.

    Args:
        modules: List of ModuleSymbol objects representing the parsed codebase

    Returns:
        str: Mermaid classDiagram syntax
    """
    lines = ["classDiagram"]

    # Check if codebase is empty
    if not modules or not any(m.classes for m in modules):
        lines.append("    %% No classes found in codebase")
        return "\n".join(lines)

    # Track all classes by their full name (module.class) for relationship lookups
    all_classes: Dict[str, tuple[str, ClassSymbol]] = {}  # class_name -> (module_name, ClassSymbol)

    # First pass: collect all classes
    for module in modules:
        module_name = _get_module_namespace_name(module.name)
        for cls in module.classes:
            all_classes[cls.name] = (module_name, cls)

    # Generate namespace blocks for each module
    for module in modules:
        if not module.classes:
            continue

        module_name = _get_module_namespace_name(module.name)
        lines.append(f"    namespace {module_name} {{")

        # Add classes with their methods
        for cls in module.classes:
            lines.append(f"        class {cls.name} {{")

            # Add methods
            for method in cls.methods:
                method_signature = _format_method_for_mermaid(method)
                lines.append(f"            {method_signature}")

            lines.append("        }")

        lines.append("    }")

    # Generate inheritance relationships
    inheritance_edges = set()
    for module in modules:
        for cls in module.classes:
            for base in cls.bases:
                # Only add edge if base class is in our codebase
                base_name = _extract_class_name(base)
                if base_name in all_classes:
                    edge = f"    {cls.name} --|> {base_name} : extends"
                    inheritance_edges.add(edge)

    # Add inheritance edges
    for edge in sorted(inheritance_edges):
        lines.append(edge)

    return "\n".join(lines)


def _get_module_namespace_name(module_path: str) -> str:
    """
    Convert a module path to a valid Mermaid namespace name.

    Examples:
        'module_a.py' -> 'sample_code_module_a'
        'src/utils.py' -> 'src_utils'
    """
    # Remove .py extension
    name = module_path.replace('.py', '')
    # Replace path separators with underscores
    name = name.replace('/', '_').replace('\\', '_')
    # Replace dots with underscores
    name = name.replace('.', '_')
    # Ensure it starts with a letter (Mermaid requirement)
    if name and not name[0].isalpha():
        name = 'module_' + name
    return name if name else 'default_module'


def _extract_class_name(base_spec: str) -> str:
    """
    Extract the simple class name from a base class specification.

    Examples:
        'BaseClass' -> 'BaseClass'
        'module.BaseClass' -> 'BaseClass'
        'pkg.module.BaseClass' -> 'BaseClass'
    """
    # Split on dots and take the last part
    parts = base_spec.split('.')
    return parts[-1]


def _format_method_for_mermaid(method: FunctionSymbol) -> str:
    """
    Format a method for Mermaid class diagram.

    Converts full signature like "compute(x: int) -> int"
    to Mermaid format like "+compute(x: int) int"

    Args:
        method: FunctionSymbol representing the method

    Returns:
        str: Mermaid-formatted method signature with visibility marker
    """
    signature = method.signature

    # Determine visibility (+ for public, - for private, # for protected)
    if method.name.startswith('__') and method.name.endswith('__'):
        visibility = '+'  # Magic methods are public
    elif method.name.startswith('__'):
        visibility = '-'  # Name-mangled private methods
    elif method.name.startswith('_'):
        visibility = '-'  # Protected/private by convention
    else:
        visibility = '+'  # Public methods

    # Extract method name and parameters
    if '(' in signature and ')' in signature:
        # Get the part before the first (
        name_part = signature[:signature.index('(')]
        # Get parameters (between parentheses)
        params_start = signature.index('(')
        params_end = signature.index(')')
        params = signature[params_start:params_end + 1]

        # Get return type if present
        return_type = ''
        if '->' in signature:
            return_part = signature.split('->')[-1].strip()
            return_type = ' ' + return_part

        return f"{visibility}{name_part}{params}{return_type}"
    else:
        # Fallback if signature is not in expected format
        return f"{visibility}{signature}"
