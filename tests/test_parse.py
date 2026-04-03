"""Tests for ``launch_interface parse``.

Each test runs the CLI against a launch file from the test workspace and
diffs the JSON output against an expected file in ``tests/expected/``.
"""
from __future__ import annotations


# 1. Simple single node (Python)
def test_simple_node(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('simple_node.launch.py'))
    assert_json(actual, 'parse_simple_node.json')


# 2. Node with parameters (Python)
def test_node_with_params(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('node_with_params.launch.py'))
    assert_json(actual, 'parse_node_with_params.json')


# 3a. Remappings and arguments — defaults
def test_remappings_and_args_defaults(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('remappings_and_args.launch.py'))
    assert_json(actual, 'parse_remappings_and_args_defaults.json')


# 3b. Remappings and arguments — overridden
def test_remappings_and_args_overridden(run_parse, launch_file_path, assert_json):
    actual = run_parse(
        launch_file_path('remappings_and_args.launch.py'),
        'node_name:=custom_node',
        'input_topic:=/custom_input',
    )
    assert_json(actual, 'parse_remappings_and_args_overridden.json')


# 4. Include chain (Python → Python)
def test_include_chain(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('include_chain.launch.py'))
    assert_json(actual, 'parse_include_chain.json')


# 5. Composable nodes (Python)
def test_composable_nodes(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('composable_nodes.launch.py'))
    assert_json(actual, 'parse_composable_nodes.json')


# 6a. Conditional nodes — condition true
def test_conditional_true(run_parse, launch_file_path, assert_json):
    actual = run_parse(
        launch_file_path('conditional_nodes.launch.py'),
        'use_node_b:=true',
    )
    assert_json(actual, 'parse_conditional_true.json')


# 6b. Conditional nodes — condition false
def test_conditional_false(run_parse, launch_file_path, assert_json):
    actual = run_parse(
        launch_file_path('conditional_nodes.launch.py'),
        'use_node_b:=false',
    )
    assert_json(actual, 'parse_conditional_false.json')


# 7. XML launch file
def test_xml_launch_file(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('simple_node.launch.xml'))
    assert_json(actual, 'parse_simple_node_xml.json')


# 8. YAML launch file
def test_yaml_launch_file(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('simple_node.launch.yaml'))
    assert_json(actual, 'parse_simple_node_yaml.json')


# 9. Namespace scoping via GroupAction
def test_namespace_scoping(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('namespace_scoping.launch.py'))
    assert_json(actual, 'parse_namespace_scoping.json')
