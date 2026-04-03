# Testing Guide

## Prerequisites

Tests require a **sourced ROS 2 installation**. The library only works in a ROS environment
and the tests run against real ROS infrastructure — no mocking.

## Running Tests

```bash
# From the launch_interface package root:
cd src/launch_interface

# Run all tests (schema tests don't need ROS, but parse/args tests do)
python3 -m pytest tests/ -v

# Run only schema validation (no ROS required)
python3 -m pytest tests/test_schema.py -v

# Run only parse or args tests
python3 -m pytest tests/test_parse.py -v
python3 -m pytest tests/test_args.py -v
```

The first run will be slow — `conftest.py` builds the test workspace via `colcon build`
once per session and caches the result. Subsequent runs reuse the build unless source files
have changed.

## Architecture

```
tests/
  conftest.py              # Session fixtures: builds test_ws, provides CLI runners
  test_parse.py            # Tests for `launch_interface parse`
  test_args.py             # Tests for `launch_interface args`
  test_schema.py           # Validates expected JSON files against schemas
  expected/                # Golden JSON files (compared against CLI output)
    parse_*.json           # Expected output for parse tests
    args_*.json            # Expected output for args tests
  test_ws/                 # Self-contained ROS 2 workspace for testing
    COLCON_IGNORE          # Prevents outer workspace from building this
    src/test_nodes/        # Minimal ROS package with dummy nodes
      launch/              # Launch files exercising various features
      params/              # Parameter YAML files
      test_nodes/          # Python node executables (node_a.py, node_b.py)
```

## How Tests Work

1. **`conftest.py`** builds `test_ws/` once per pytest session, sources
   `test_ws/install/setup.bash`, and captures the resulting environment.

2. **`test_parse.py`** and **`test_args.py`** call the CLI via subprocess using that
   environment. Each test runs `launch_interface parse` or `launch_interface args` against
   a launch file and compares the JSON output to a golden file in `expected/`.

3. **Path normalisation**: Absolute paths in CLI output are replaced with `<TEST_WS>` and
   `<INSTALL>` placeholders before comparison, so expected files are portable.

4. **`cmd` field handling**: The `cmd` arrays in expected files are documentation only — the
   test harness checks that `cmd` is present and non-empty but does not compare its contents
   (exact command lines vary by platform/install path).

5. **`test_schema.py`** validates every `expected/*.json` file against the JSON schemas in
   `schema/`. This is parametrized — new expected files are picked up automatically.

## Test Matrix

### `test_parse.py`

| Test | Launch file | Exercises |
|------|-------------|-----------|
| `test_simple_node` | `simple_node.launch.py` | Basic `Node`, name, namespace, package, executable |
| `test_node_with_params` | `node_with_params.launch.py` | `--params-file`, inline params, parameter merging |
| `test_remappings_and_args_defaults` | `remappings_and_args.launch.py` | `DeclareLaunchArgument`, `LaunchConfiguration`, remappings (defaults) |
| `test_remappings_and_args_overridden` | `remappings_and_args.launch.py` | Same, with args overridden via CLI |
| `test_include_chain` | `include_chain.launch.py` | `IncludeLaunchDescription`, source file tracking, arg passing |
| `test_composable_nodes` | `composable_nodes.launch.py` | `ComposableNodeContainer` + `LoadComposableNodes` |
| `test_conditional_true` | `conditional_nodes.launch.py` | `IfCondition` true — conditional node present |
| `test_conditional_false` | `conditional_nodes.launch.py` | `UnlessCondition` — conditional node absent, unless node present |
| `test_xml_launch_file` | `simple_node.launch.xml` | XML frontend |
| `test_yaml_launch_file` | `simple_node.launch.yaml` | YAML frontend |
| `test_namespace_scoping` | `namespace_scoping.launch.py` | `GroupAction` + `PushRosNamespace` |
| `test_missing_required_arg` | `required_arg.launch.py` | Non-zero exit when required arg not provided |
| `test_execute_process` | `execute_process.launch.py` | Raw `ExecuteProcess` excluded, only `Node` extracted |
| `test_multiple_nodes` | `multiple_nodes.launch.py` | 3 nodes — verifies ordering preserved |
| `test_on_process_exit` | `on_process_exit.launch.py` | `OnProcessExit` event handler triggers second node |
| `test_include_xml` | `include_xml.launch.py` | Python including XML via `AnyLaunchDescriptionSource` |
| `test_nested_include` | `nested_include_root.launch.py` | 3-level include chain, nested include tree |
| `test_opaque_function` | `opaque_function.launch.py` | `OpaqueFunction` dynamically creates a node |
| `test_param_override` | `param_override.launch.py` | Parameter merge order: wildcard < node-specific < inline |
| `test_env_var_substitution` | `env_var_substitution.launch.py` | `EnvironmentVariable` substitution |

### `test_args.py`

| Test | Launch file | Exercises |
|------|-------------|-----------|
| `test_args_simple_node` | `simple_node.launch.py` | No declared arguments → empty list |
| `test_args_remappings_and_args` | `remappings_and_args.launch.py` | Arguments with defaults |
| `test_args_conditional_nodes` | `conditional_nodes.launch.py` | Conditional launch file arguments |
| `test_args_include_chain` | `include_chain.launch.py` | Included file's args don't leak to root |
| `test_args_required_arg` | `required_arg.launch.py` | Required arg (no default) has `"default": null` |

### `test_schema.py`

Parametrized over all files in `expected/`. Validates `parse_*.json` against
`schema/parse.schema.json` and `args_*.json` against `schema/args.schema.json`.
New expected files are picked up automatically.

## Adding a New Test Case

1. **Create a launch file** in `tests/test_ws/src/test_nodes/launch/`. The `setup.py` uses
   `glob('launch/*')` so new files are installed automatically.

2. **Create parameter files** (if needed) in `tests/test_ws/src/test_nodes/params/`. Same
   glob pattern applies.

3. **Create the expected JSON** in `tests/expected/`. Name it `parse_<name>.json` or
   `args_<name>.json`. Use `<TEST_WS>` and `<INSTALL>` placeholders for paths. The `cmd`
   field is documentation only — include a representative value but it won't be compared.

4. **Validate against the schema**: run `python3 -m pytest tests/test_schema.py -v` to
   confirm the expected JSON conforms to the schema.

5. **Add the test function** in `test_parse.py` or `test_args.py`:
   ```python
   def test_my_feature(run_parse, launch_file_path, assert_json):
       actual = run_parse(launch_file_path('my_feature.launch.py'))
       assert_json(actual, 'parse_my_feature.json')
   ```

6. **Rebuild the test workspace** if you added new launch/param files — delete
   `tests/test_ws/install/` or just run the tests (conftest detects source changes).

## Error Tests

For tests that expect failure (e.g. missing required argument), use `subprocess` directly
instead of the `run_parse` fixture (which asserts success):

```python
def test_my_error_case(test_ws_env, launch_file_path):
    result = subprocess.run(
        [sys.executable, '-m', 'launch_interface', 'parse',
         launch_file_path('my_error_case.launch.py')],
        capture_output=True,
        text=True,
        env=test_ws_env,
    )
    assert result.returncode != 0
```

## Schemas

JSON schemas live in `schema/` at the package root:

- `parse.schema.json` — schema for `launch_interface parse` output
- `args.schema.json` — schema for `launch_interface args` output

If you change the output format, update the schema, update any affected expected files, and
run `test_schema.py` to verify consistency.
