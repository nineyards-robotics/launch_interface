"""CLI entry point for launch_interface.

Usage:
    launch_interface parse <launch_file> [key:=value ...]
    launch_interface args <launch_file>
"""
from __future__ import annotations

import json
import sys


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
    print(json.dumps({}))


def _cmd_args(args: list[str]) -> None:
    print(json.dumps([]))
