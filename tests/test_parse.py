"""Tests for ``launch_interface parse``.

Each test runs the CLI against a launch file from the test workspace and
diffs the JSON output against an expected file in ``tests/expected/``.
"""
from __future__ import annotations

import subprocess
import sys


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


# --------------------------------------------------------------------------
# New test cases
# --------------------------------------------------------------------------


# 10. Missing required launch argument — should fail with non-zero exit
def test_missing_required_arg(test_ws_env, launch_file_path):
    result = subprocess.run(
        [sys.executable, '-m', 'launch_interface', 'parse',
         launch_file_path('required_arg.launch.py')],
        capture_output=True,
        text=True,
        env=test_ws_env,
    )
    assert result.returncode != 0, (
        'parse should fail when a required launch argument is not provided'
    )


# 11. ExecuteProcess (non-Node) — raw ExecuteProcess excluded, only Node extracted
def test_execute_process(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('execute_process.launch.py'))
    assert_json(actual, 'parse_execute_process.json')


# 12. Multiple nodes in a single launch file — ordering preserved
def test_multiple_nodes(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('multiple_nodes.launch.py'))
    assert_json(actual, 'parse_multiple_nodes.json')


# 13. OnProcessExit — node launched by event handler is captured
def test_on_process_exit(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('on_process_exit.launch.py'))
    assert_json(actual, 'parse_on_process_exit.json')


# 14. Include XML from Python — cross-format include
def test_include_xml(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('include_xml.launch.py'))
    assert_json(actual, 'parse_include_xml.json')


# 15. Nested includes (root → mid → included) — deep include tree
def test_nested_include(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('nested_include_root.launch.py'))
    assert_json(actual, 'parse_nested_include.json')


# 16. OpaqueFunction — dynamically created node is captured
def test_opaque_function(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('opaque_function.launch.py'))
    assert_json(actual, 'parse_opaque_function.json')


# 17. Parameter merge order — wildcard < node-specific < inline
def test_param_override(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('param_override.launch.py'))
    assert_json(actual, 'parse_param_override.json')


# 18. EnvironmentVariable substitution — node name from env var
def test_env_var_substitution(run_parse, launch_file_path, assert_json):
    actual = run_parse(launch_file_path('env_var_substitution.launch.py'))
    assert_json(actual, 'parse_env_var.json')
