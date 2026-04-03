"""Serialisation of LaunchModel to JSON-compatible dicts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .model import (
    ComposableNodeInfo,
    ContainerInfo,
    IncludeInfo,
    InlineParamSource,
    LaunchModel,
    NodeInfo,
    ParamFileSource,
)


def _param_source_to_dict(source) -> dict[str, Any]:
    if isinstance(source, ParamFileSource):
        return {"type": "file", "path": str(source.path)}
    elif isinstance(source, InlineParamSource):
        return {"type": "inline", "name": source.name, "value": source.value}
    return {}


def _composable_node_to_dict(cn: ComposableNodeInfo) -> dict[str, Any]:
    return {
        "type": cn.node_type.value,
        "package": cn.package,
        "plugin": cn.plugin,
        "name": cn.name,
        "namespace": cn.namespace,
        "fully_qualified_name": cn.fully_qualified_name,
        "remappings": [list(r) for r in cn.remappings],
        "parameters": cn.parameters,
        "extra_arguments": cn.extra_arguments,
        "source_file": str(cn.source_file) if cn.source_file else None,
    }


def _node_to_dict(node: NodeInfo | ContainerInfo) -> dict[str, Any]:
    d: dict[str, Any] = {
        "type": node.node_type.value,
        "package": node.package,
        "executable": node.executable,
        "name": node.name,
        "namespace": node.namespace,
        "fully_qualified_name": node.fully_qualified_name,
        "remappings": [list(r) for r in node.remappings],
        "parameter_sources": [_param_source_to_dict(s) for s in node.parameter_sources],
        "parameters": node.parameters if node.parameters is not None else {},
        "cmd": node.cmd,
        "source_file": str(node.source_file) if node.source_file else None,
    }
    if isinstance(node, ContainerInfo):
        d["composable_nodes"] = [
            _composable_node_to_dict(cn) for cn in node.composable_nodes
        ]
    return d


def _include_to_dict(inc: IncludeInfo) -> dict[str, Any]:
    return {
        "source_file": str(inc.source_file),
        "included_file": str(inc.included_file),
        "launch_arguments": inc.launch_arguments,
        "includes": [_include_to_dict(child) for child in inc.includes],
    }


def to_dict(model: LaunchModel) -> dict[str, Any]:
    return {
        "launch_file": str(model.launch_file),
        "launch_arguments": model.launch_arguments,
        "declared_arguments": model.declared_arguments,
        "nodes": [_node_to_dict(n) for n in model.nodes],
        "includes": [_include_to_dict(i) for i in model.includes],
    }


def to_json(model: LaunchModel, **kwargs) -> str:
    return json.dumps(to_dict(model), **kwargs)
