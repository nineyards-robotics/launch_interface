"""Data model for the resolved launch graph."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NodeType(Enum):
    NODE = "node"
    COMPOSABLE_NODE_CONTAINER = "composable_node_container"
    COMPOSABLE_NODE = "composable_node"


@dataclass
class ParamFileSource:
    path: Path
    contents: dict[str, Any] | None = None

@dataclass
class InlineParamSource:
    name: str
    value: Any


ParamSource = ParamFileSource | InlineParamSource


@dataclass
class NodeInfo:
    node_type: NodeType
    package: str
    executable: str
    name: str | None
    namespace: str
    fully_qualified_name: str | None
    parameter_sources: list[ParamSource]
    parameters: dict[str, Any] | None = None
    remappings: list[tuple[str, str]] = field(default_factory=list)
    additional_args: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)
    source_file: Path | None = None


@dataclass
class ComposableNodeInfo:
    node_type: NodeType = field(default=NodeType.COMPOSABLE_NODE, init=False)
    package: str = ""
    plugin: str = ""
    name: str | None = None
    namespace: str = ""
    fully_qualified_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    remappings: list[tuple[str, str]] = field(default_factory=list)
    extra_arguments: dict[str, Any] = field(default_factory=dict)
    source_file: Path | None = None


@dataclass
class ContainerInfo(NodeInfo):
    node_type: NodeType = field(default=NodeType.COMPOSABLE_NODE_CONTAINER, init=False)
    composable_nodes: list[ComposableNodeInfo] = field(default_factory=list)


@dataclass
class IncludeInfo:
    source_file: Path
    included_file: Path
    launch_arguments: dict[str, str]
    includes: list[IncludeInfo] = field(default_factory=list)


@dataclass
class LaunchModel:
    launch_file: Path
    launch_arguments: dict[str, str]
    nodes: list[NodeInfo | ContainerInfo] = field(default_factory=list)
    includes: list[IncludeInfo] = field(default_factory=list)
    declared_arguments: dict[str, str | None] = field(default_factory=dict)
