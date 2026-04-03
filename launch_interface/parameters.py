"""Layer 3: Parameter resolver.

Loads --params-file YAML files and merges parameter sources to produce
a final parameter dictionary per node.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .model import InlineParamSource, NodeInfo, ParamFileSource


def _load_param_yaml(
    path: Path,
    fully_qualified_name: str | None,
    pre_loaded: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load parameters from a YAML file for a specific node.

    The YAML file uses the ROS 2 parameter file format where parameters
    are namespaced under node FQNs with a ``ros__parameters`` key.
    A ``/**`` wildcard applies to all nodes.
    """
    if pre_loaded is not None:
        data = pre_loaded
    else:
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except Exception:
            return {}

    if not isinstance(data, dict):
        return {}

    merged: dict[str, Any] = {}

    # Wildcard parameters (/**)
    wildcard = data.get('/**', {})
    if isinstance(wildcard, dict):
        ros_params = wildcard.get('ros__parameters', {})
        if isinstance(ros_params, dict):
            merged.update(ros_params)

    # Node-specific parameters
    if fully_qualified_name:
        node_section = data.get(fully_qualified_name, {})
        if isinstance(node_section, dict):
            ros_params = node_section.get('ros__parameters', {})
            if isinstance(ros_params, dict):
                merged.update(ros_params)

    return merged


def resolve_parameters(
    node_info: NodeInfo,
    temp_file_contents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge all parameter sources for a node into a final dict."""
    merged: dict[str, Any] = {}

    for source in node_info.parameter_sources:
        if isinstance(source, ParamFileSource):
            # Check if we have pre-loaded contents (for temp files)
            pre_loaded = None
            if temp_file_contents:
                pre_loaded = temp_file_contents.get(str(source.path))
            params = _load_param_yaml(
                source.path,
                node_info.fully_qualified_name,
                pre_loaded=pre_loaded,
            )
            merged.update(params)
        elif isinstance(source, InlineParamSource):
            merged[source.name] = source.value

    return merged
