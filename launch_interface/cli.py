"""CLI entry point for launch_interface.

Usage:
    launch_interface parse <launch_file> [key:=value ...]
    launch_interface args <launch_file>
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print('Usage: launch_interface {parse,args} <launch_file> [key:=value ...]', file=sys.stderr)
        sys.exit(1)

    command = args[0]
    if command == 'parse':
        _cmd_parse(args[1:])
    elif command == 'args':
        _cmd_args(args[1:])
    else:
        print(f'Unknown command: {command}', file=sys.stderr)
        sys.exit(1)


def _cmd_parse(args: list[str]) -> None:
    if not args:
        print('Usage: launch_interface parse <launch_file> [key:=value ...]', file=sys.stderr)
        sys.exit(1)

    launch_file = args[0]
    launch_arguments: dict[str, str] = {}
    for arg in args[1:]:
        if ':=' in arg:
            key, _, value = arg.partition(':=')
            launch_arguments[key] = value

    try:
        from .dry_run import dry_run
        from .extractor import extract
        from .parameters import resolve_parameters
        from .serialise import to_dict

        result = dry_run(
            launch_file,
            launch_arguments=launch_arguments if launch_arguments else None,
        )

        model = extract(result)
        model.launch_file = Path(launch_file).resolve()
        model.launch_arguments = launch_arguments

        # Resolve parameters for all nodes
        for node in model.nodes:
            # Use all param sources (including temp files) for resolution
            all_sources = getattr(node, '_all_param_sources', node.parameter_sources)
            original_sources = node.parameter_sources
            node.parameter_sources = all_sources
            node.parameters = resolve_parameters(node)
            node.parameter_sources = original_sources

        output = to_dict(model)
        print(json.dumps(output))

    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _cmd_args(args: list[str]) -> None:
    if not args:
        print('Usage: launch_interface args <launch_file>', file=sys.stderr)
        sys.exit(1)

    launch_file = args[0]

    try:
        from launch.actions import DeclareLaunchArgument
        from launch.substitutions import TextSubstitution
        from .dry_run import _load_launch_description

        ld = _load_launch_description(Path(launch_file).resolve())

        result = []
        for entity in ld.entities:
            if isinstance(entity, DeclareLaunchArgument):
                default = entity.default_value
                if default is not None:
                    parts = []
                    for sub in default:
                        if isinstance(sub, TextSubstitution):
                            parts.append(sub.text)
                        else:
                            parts.append(str(sub))
                    default = ''.join(parts)

                result.append({
                    'name': entity.name,
                    'default': default,
                    'description': entity.description,
                })

        print(json.dumps(result))

    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
