# launch_interface

Dry-run execution of ROS 2 launch files with structured JSON output.

`launch_interface` reads a ROS 2 launch file through the real `LaunchService` pipeline — resolving all substitutions, conditionals, includes, and scoping — without actually starting any nodes or making ROS service calls. The result is a fully-resolved JSON representation of the launch graph, suitable for consumption by dev tools, IDE integrations, linters, and visualizers.

## Features

- Resolves the full launch graph including nested includes, conditionals, namespacing, remappings, and parameter files
- Supports all three launch formats: Python (`.launch.py`), XML (`.launch.xml`), and YAML (`.launch.yaml`)
- Handles composable nodes, `OpaqueFunction`, `OnProcessExit` handlers, and `CommandSubstitution`
- Tracks which source file each node originates from
- Merges parameters from YAML files and inline sources with correct override semantics
- Outputs machine-readable JSON (schemas in `schema/`)

## Example

Given a launch file:

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='param_node',
            namespace='/test_ns',
            parameters=[
                '/path/to/params.yaml',
                {'inline_param': 'hello', 'inline_int': 42},
            ],
        ),
    ])
```

Running `launch_interface parse node_with_params.launch.py` produces:

```json
{
  "launch_file": "/path/to/node_with_params.launch.py",
  "launch_arguments": {},
  "declared_arguments": {},
  "nodes": [
    {
      "type": "node",
      "package": "test_nodes",
      "executable": "node_a",
      "name": "param_node",
      "namespace": "/test_ns",
      "fully_qualified_name": "/test_ns/param_node",
      "remappings": [],
      "parameter_sources": [
        {
          "type": "file",
          "path": "/path/to/params.yaml"
        }
      ],
      "parameters": {
        "file_param_str": "from_file",
        "file_param_int": 100,
        "wildcard_param": "applies_to_all",
        "inline_param": "hello",
        "inline_int": 42
      },
      "cmd": ["ros2", "run", "test_nodes", "node_a", "--ros-args", ...],
      "source_file": "/path/to/node_with_params.launch.py"
    }
  ],
  "includes": []
}
```

## Installation

### pip

```bash
pip install git+https://github.com/nineyards-robotics/launch_interface.git
```

### colcon (ROS 2 workspace)

```bash
# Clone into your workspace src/ directory
cd ~/your_ws/src
git clone https://github.com/nineyards-robotics/launch_interface.git

# Build and source
cd ~/your_ws
colcon build --packages-select launch_interface
source install/setup.bash
```

### Dependencies

- `ros2launch`
- `launch_ros`

## Usage

### Parse a launch file

```bash
launch_interface parse <launch_file> [key:=value ...]
```

Performs a full dry-run of the launch file and outputs the resolved launch graph as JSON to stdout.

```bash
launch_interface parse robot.launch.py use_sim:=true robot_name:=atlas
```

### List declared arguments

```bash
launch_interface args <launch_file>
```

Outputs declared launch arguments (with defaults and descriptions) as JSON.

### Python API

```python
from launch_interface.dry_run import dry_run
from launch_interface.extractor import extract
from launch_interface.parameters import resolve_parameters
from launch_interface.serialise import to_json

result = dry_run("robot.launch.py", launch_arguments={"use_sim": "true"})
model = extract(result)
for node in model.nodes:
    node.parameters = resolve_parameters(node)
print(to_json(model))
```

## Output structure

The `parse` command produces a JSON object with:

| Field | Description |
|---|---|
| `launch_file` | Absolute path to the launch file |
| `launch_arguments` | Arguments passed to the launch file |
| `declared_arguments` | Arguments declared in the launch file with defaults and descriptions |
| `nodes` | List of resolved nodes (regular nodes and composable node containers) |
| `includes` | Nested tree of included launch files |

Each node includes its package, executable, fully qualified name, resolved parameters, remappings, full command line, and source file. Composable node containers additionally list their loaded composable nodes with plugin names and resolved parameters.

Full JSON schemas are in `schema/parse.schema.json` and `schema/args.schema.json`.

## Architecture

The library uses a three-layer pipeline:

1. **Dry-run executor** (`dry_run.py`) — Runs the launch file through the real ROS 2 `LaunchService`, patching `ExecuteLocal` and `LoadComposableNodes` to prevent process spawning and service calls while capturing all resolved entity data.

2. **Entity extractor** (`extractor.py`) — Walks the collected entities and builds a structured `LaunchModel` with node info, include trees, and declared arguments.

3. **Parameter resolver** (`parameters.py`) — Loads and merges YAML parameter files with inline parameter sources, respecting ROS 2 wildcard (`/**`) and node-specific namespacing.

## Testing

Tests require a sourced ROS 2 installation. The test workspace is built automatically by `conftest.py` on the first run.

```bash
# Run all tests
python3 -m pytest tests/ -v

# Schema validation only (no ROS required)
python3 -m pytest tests/test_schema.py -v
```

See `tests/TESTING.md` for the full testing guide.

## License

Apache-2.0
