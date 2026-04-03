"""Tests for ``launch_interface args``.

Each test runs the CLI against a launch file and diffs the JSON output
against an expected file in ``tests/expected/``.
"""
from __future__ import annotations


# No arguments declared
def test_args_simple_node(run_args, launch_file_path, assert_json):
    actual = run_args(launch_file_path('simple_node.launch.py'))
    assert_json(actual, 'args_simple_node.json')


# Arguments with defaults
def test_args_remappings_and_args(run_args, launch_file_path, assert_json):
    actual = run_args(launch_file_path('remappings_and_args.launch.py'))
    assert_json(actual, 'args_remappings_and_args.json')


# Conditional launch file arguments
def test_args_conditional_nodes(run_args, launch_file_path, assert_json):
    actual = run_args(launch_file_path('conditional_nodes.launch.py'))
    assert_json(actual, 'args_conditional_nodes.json')
