"""Layer 2: Entity extractor.

Walks the collected entities from Layer 1 and builds a structured LaunchModel.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from launch.actions import DeclareLaunchArgument, ExecuteLocal
from launch_ros.actions import ComposableNodeContainer, Node

from .dry_run import DryRunRegistry, DryRunResult
from .model import (
    ComposableNodeInfo,
    ContainerInfo,
    IncludeInfo,
    InlineParamSource,
    LaunchModel,
    NodeInfo,
    NodeType,
    ParamFileSource,
    ParamSource,
)


def _extract_package_and_executable(action: ExecuteLocal, context: Any) -> tuple[str, str]:
    """Extract resolved package and executable from a Node action."""
    if isinstance(action, Node):
        try:
            pkg = action.node_package
            exe = action.node_executable
            # May be a string or a list of substitutions depending on ROS version
            if isinstance(pkg, str):
                package = pkg
            else:
                from launch.utilities import perform_substitutions
                package = perform_substitutions(context, pkg)
            if isinstance(exe, str):
                executable = exe
            else:
                from launch.utilities import perform_substitutions
                executable = perform_substitutions(context, exe)
            return package, executable
        except Exception:
            pass

    return "", ""


def _extract_name_and_namespace(action: Node) -> tuple[str | None, str, str | None]:
    """Extract resolved name, namespace, and fully qualified name."""
    try:
        fqn = action.node_name
        if fqn:
            parts = fqn.rsplit('/', 1)
            if len(parts) == 2:
                namespace = parts[0] if parts[0] else '/'
                name = parts[1]
            else:
                namespace = '/'
                name = parts[0]
            return name, namespace, fqn
    except Exception:
        pass

    return None, '/', None


def _extract_remappings(action: Node) -> list[tuple[str, str]]:
    """Extract resolved remapping rules."""
    try:
        rules = action.expanded_remapping_rules
        if rules:
            # Filter out internal remappings (__node, __ns)
            return [
                (src, dst) for src, dst in rules
                if not src.startswith('__')
            ]
    except Exception:
        pass
    return []


def _is_temp_param_file(path: str) -> bool:
    """Check if a params file is a temp file generated from an inline dict."""
    import tempfile
    tmp_dir = tempfile.gettempdir()
    return path.startswith(tmp_dir + '/launch_params_') or path.startswith(tmp_dir + '\\launch_params_')


def _extract_parameter_sources(action: ExecuteLocal) -> tuple[list[ParamSource], list[ParamFileSource]]:
    """Extract parameter sources from the resolved command line.

    Returns (visible_sources, temp_sources) where visible_sources are
    user-specified param files and inline params, and temp_sources are
    param files generated from inline dicts (for parameter resolution only).
    """
    try:
        cmd = action.process_details.get('cmd', [])
    except (AttributeError, TypeError):
        cmd = []

    if not cmd:
        try:
            cmd = list(action.cmd) if action.cmd else []
        except Exception:
            return [], []

    cmd = [str(c) for c in cmd]
    visible: list[ParamSource] = []
    temp: list[ParamFileSource] = []
    i = 0
    in_ros_args = False

    while i < len(cmd):
        arg = cmd[i]
        if arg == '--ros-args':
            in_ros_args = True
            i += 1
            continue

        if not in_ros_args:
            i += 1
            continue

        if arg == '--':
            in_ros_args = False
            i += 1
            continue

        if arg == '--params-file' and i + 1 < len(cmd):
            path = cmd[i + 1]
            pfs = ParamFileSource(path=Path(path))
            if _is_temp_param_file(path):
                temp.append(pfs)
            else:
                visible.append(pfs)
            i += 2
        elif arg == '-p' and i + 1 < len(cmd):
            param_str = cmd[i + 1]
            if ':=' in param_str:
                name, _, value_str = param_str.partition(':=')
                value = _parse_yaml_scalar(value_str)
                visible.append(InlineParamSource(name=name, value=value))
            i += 2
        else:
            i += 1

    return visible, temp


def _parse_yaml_scalar(value: str) -> Any:
    """Parse a YAML scalar string into a Python value."""
    import yaml
    try:
        return yaml.safe_load(value)
    except Exception:
        return value


def _extract_cmd(action: ExecuteLocal) -> list[str]:
    """Extract the full resolved command line."""
    try:
        cmd = action.process_details.get('cmd', [])
        if cmd:
            return [str(c) for c in cmd]
    except (AttributeError, TypeError):
        pass

    try:
        if action.cmd:
            return [str(c) for c in action.cmd]
    except Exception:
        pass

    return []


def _is_node_action(action: ExecuteLocal) -> bool:
    """Check if this is a Node (or subclass) action vs raw ExecuteProcess."""
    return isinstance(action, Node)


def _convert_include(record) -> IncludeInfo:
    """Convert a DryRunRegistry IncludeRecord to an IncludeInfo."""
    return IncludeInfo(
        source_file=record.source_file,
        included_file=record.included_file,
        launch_arguments=record.launch_arguments,
        includes=[_convert_include(child) for child in record.children],
    )


def extract(result: DryRunResult) -> LaunchModel:
    """Build a LaunchModel from a DryRunResult."""
    registry = result.registry
    context = result.context

    model = LaunchModel(
        launch_file=Path(result.launch_description.entities[0].__class__.__name__)
        if not hasattr(result, '_launch_file') else result._launch_file,
        launch_arguments={},
    )

    # Extract nodes from process actions
    container_names: set[str] = set()
    containers: dict[str, ContainerInfo] = {}

    for action in registry.process_actions:
        if not _is_node_action(action):
            continue

        name, namespace, fqn = _extract_name_and_namespace(action)
        package, executable = _extract_package_and_executable(action, context)
        remappings = _extract_remappings(action)
        visible_sources, temp_sources = _extract_parameter_sources(action)
        cmd = _extract_cmd(action)
        source_file = registry.entity_source_files.get(id(action))

        # For parameter resolution, we need all sources (visible + temp)
        all_sources = list(visible_sources) + list(temp_sources)

        if isinstance(action, ComposableNodeContainer):
            container = ContainerInfo(
                package=package,
                executable=executable,
                name=name,
                namespace=namespace,
                fully_qualified_name=fqn,
                remappings=remappings,
                parameter_sources=visible_sources,
                cmd=cmd,
                source_file=Path(source_file) if source_file else None,
            )
            # Stash all sources for parameter resolution
            container._all_param_sources = all_sources
            model.nodes.append(container)
            if fqn:
                containers[fqn] = container
                container_names.add(fqn)
        else:
            node = NodeInfo(
                node_type=NodeType.NODE,
                package=package,
                executable=executable,
                name=name,
                namespace=namespace,
                fully_qualified_name=fqn,
                remappings=remappings,
                parameter_sources=visible_sources,
                cmd=cmd,
                source_file=Path(source_file) if source_file else None,
            )
            # Stash all sources for parameter resolution
            node._all_param_sources = all_sources
            model.nodes.append(node)

    # Attach composable nodes to their containers
    for container_name, records in registry.composable_nodes.items():
        container = containers.get(container_name)
        for record in records:
            req = record.request
            if req is None:
                continue

            cn_name = req.node_name if req.node_name else None
            cn_namespace = req.node_namespace if req.node_namespace else ''

            # Build FQN
            if cn_name:
                if cn_namespace and cn_namespace != '/':
                    cn_fqn = f'{cn_namespace}/{cn_name}'
                else:
                    cn_fqn = f'/{cn_name}'
            else:
                cn_fqn = None

            # Extract parameters from the request
            cn_params = {}
            if req.parameters:
                for param in req.parameters:
                    cn_params[param.name] = _parameter_value_to_python(param.value)

            # Extract remappings
            cn_remappings = []
            if req.remap_rules:
                for rule in req.remap_rules:
                    if ':=' in rule:
                        src, _, dst = rule.partition(':=')
                        cn_remappings.append((src, dst))

            # Extract extra arguments
            cn_extra = {}
            if req.extra_arguments:
                for param in req.extra_arguments:
                    cn_extra[param.name] = _parameter_value_to_python(param.value)

            source_file = registry.entity_source_files.get(id(record))

            cn_info = ComposableNodeInfo(
                package=req.package_name,
                plugin=req.plugin_name,
                name=cn_name,
                namespace=cn_namespace,
                fully_qualified_name=cn_fqn,
                parameters=cn_params,
                remappings=cn_remappings,
                extra_arguments=cn_extra,
                source_file=Path(source_file) if source_file else None,
            )

            if container is not None:
                container.composable_nodes.append(cn_info)

    # Convert includes
    model.includes = [_convert_include(rec) for rec in registry.includes]

    # Extract declared arguments from the launch description
    model.declared_arguments = _extract_declared_arguments(result.launch_description)

    return model


def _parameter_value_to_python(value: Any) -> Any:
    """Convert an rcl_interfaces ParameterValue to a Python value."""
    from rcl_interfaces.msg import ParameterType

    if hasattr(value, 'type'):
        t = value.type
        if t == ParameterType.PARAMETER_BOOL:
            return value.bool_value
        elif t == ParameterType.PARAMETER_INTEGER:
            return value.integer_value
        elif t == ParameterType.PARAMETER_DOUBLE:
            return value.double_value
        elif t == ParameterType.PARAMETER_STRING:
            return value.string_value
        elif t == ParameterType.PARAMETER_BYTE_ARRAY:
            return list(value.byte_array_value)
        elif t == ParameterType.PARAMETER_BOOL_ARRAY:
            return list(value.bool_array_value)
        elif t == ParameterType.PARAMETER_INTEGER_ARRAY:
            return list(value.integer_array_value)
        elif t == ParameterType.PARAMETER_DOUBLE_ARRAY:
            return list(value.double_array_value)
        elif t == ParameterType.PARAMETER_STRING_ARRAY:
            return list(value.string_array_value)
    return None


def _extract_declared_arguments(launch_description) -> dict[str, dict[str, str | None]]:
    """Extract declared launch arguments from a launch description."""
    args: dict[str, dict[str, str | None]] = {}
    for entity in launch_description.entities:
        if isinstance(entity, DeclareLaunchArgument):
            name = entity.name
            default = entity.default_value
            if default is not None:
                # default_value is a list of substitutions — we need to
                # render them to string. For simple defaults they're
                # typically [TextSubstitution].
                from launch.substitutions import TextSubstitution
                default_parts = []
                for sub in default:
                    if isinstance(sub, TextSubstitution):
                        default_parts.append(sub.text)
                    else:
                        default_parts.append(str(sub))
                default = ''.join(default_parts)
            args[name] = {
                'default': default,
                'description': entity.description,
            }
    return args
