# launch_interface Design Document

## Overview

`launch_interface` is a Python library for reading (via dry-run execution) and writing ROS 2
launch files. It produces a structured, fully-resolved representation of the launch graph —
node names, namespaces, parameters, remappings, composable node relationships, and include
structure — without actually starting any ROS nodes.

The library targets dev-tool use cases (IDE integrations, linters, visualisers, code
generators) and is designed to be called from TypeScript (via subprocess + JSON) and Python
directly.

### Why dry-run execution?

ROS 2 launch supports three frontend syntaxes (Python, XML, YAML), all of which produce a
`LaunchDescription` — a tree of `Action` objects containing unresolved `Substitution` objects.
Substitutions are resolved **lazily** inside `Action.execute(context)` as the `LaunchContext`
accumulates state from prior actions (one action's output feeds the next action's
substitutions). Conditionals, scoping (`GroupAction`), and includes also depend on runtime
context.

This means there is no way to get a fully-resolved launch tree without simulating execution.
The existing `ros2 launch --print` flag only shows the static, unresolved tree via
`LaunchIntrospector` — substitutions appear as objects, not values.

Our approach: run the real launch execution pipeline, but intercept at the process-spawning
layer so nothing actually starts.


## Architecture

```
                    Launch File (.py / .xml / .yaml)
                                |
                                v
                    +------------------------+
                    |    Layer 1: Dry Run     |
                    |      (dry_run.py)       |
                    |                         |
                    |  - Patches process      |
                    |    spawning to no-op    |
                    |  - Patches composable   |
                    |    node loading         |
                    |  - Runs LaunchService   |
                    |  - Collects visited     |
                    |    entities             |
                    +------------------------+
                                |
                      List[LaunchDescriptionEntity]
                                |
                                v
                    +------------------------+
                    |  Layer 2: Extraction    |
                    |    (extractor.py)       |
                    |                         |
                    |  - Walks entity list    |
                    |  - Reads resolved       |
                    |    attributes from      |
                    |    Node, ExecuteProcess, |
                    |    ComposableNode, etc. |
                    |  - Builds structured    |
                    |    model                |
                    +------------------------+
                                |
                          LaunchModel
                                |
                                v
                    +------------------------+
                    |  Layer 3: Parameters    |
                    |    (parameters.py)      |
                    |                         |
                    |  - Loads --params-file  |
                    |    YAML files           |
                    |  - Merges parameter     |
                    |    sources in order     |
                    |  - Produces final       |
                    |    parameter dict per   |
                    |    node                 |
                    +------------------------+
                                |
                          LaunchModel (enriched)
```


## Layer 1: Dry-Run Executor (`dry_run.py`)

### Purpose

Execute a launch file through the real `LaunchService` pipeline, resolving all substitutions,
conditionals, includes, and scoping — but prevent any OS processes from being spawned and any
ROS service calls from being made.

### Interception Points

There are exactly **two** things we need to prevent:

#### 1. Process spawning — `ExecuteLocal.__execute_process()`

This is the async method that calls `osrf_pycommon.async_execute_process()` to create the OS
subprocess. Everything before it in the `execute()` call chain is pure substitution resolution
and state setup:

```
ExecuteLocal.execute()
  -> self.prepare(context)          # resolves ALL substitutions
  -> registers event handlers       # context state management
  -> creates __completed_future     # lifecycle tracking
  -> asyncio.create_task(           # <-- THIS spawns the process
       self.__execute_process(context))
```

We replace `__execute_process` with a coroutine that immediately signals completion:

```python
async def _noop_execute_process(self, context):
    # prepare() already ran — all substitutions are resolved.
    # Signal completion so LaunchService reaches idle and shuts down.
    self._ExecuteLocal__cleanup()
```

Applied via: `ExecuteLocal._ExecuteLocal__execute_process = _noop_execute_process`

This preserves:
- `prepare()` → all substitution resolution
- Event handler registration → correct context state
- `__completed_future` lifecycle → clean LaunchService shutdown

#### 2. Composable node loading — `LoadComposableNodes.execute()`

`LoadComposableNodes` does not spawn a process. Instead, it makes **ROS service calls** to a
running container node to load component plugins. In a dry run the container is not running,
so this would hang forever.

However, the composable node information we need is available *before* the service call.
`LoadComposableNodes.execute()` calls `get_composable_node_load_request()` for each
`ComposableNode` description, which fully resolves package, plugin, name, namespace,
parameters, and remappings.

We replace `execute()` with a version that resolves the descriptions but skips the service
call:

```python
def _dry_run_load_composable_nodes(self, context):
    # Resolve the target container name
    container_name = _resolve_container_name(self, context)

    # For each ComposableNode, build the resolved request (resolves all substitutions)
    for node_desc in self._LoadComposableNodes__composable_node_descriptions:
        if node_desc.condition() is None or node_desc.condition().evaluate(context):
            request = get_composable_node_load_request(node_desc, context)
            # Store for collection (see Entity Collection below)
            _dry_run_registry.record_composable_node(container_name, node_desc, request)
```

### Entity Collection

During the dry run, we need to capture references to all visited entities so Layer 2 can
extract data from them. Two collection mechanisms:

1. **Process-based entities** (`Node`, `ExecuteProcess`, `ComposableNodeContainer`): We wrap
   the patched `__execute_process` to also register `self` in a collection list before calling
   cleanup. After the dry run, we have a flat list of every `ExecuteLocal`-derived action that
   was visited and resolved.

2. **Composable node descriptions**: Collected via the patched `LoadComposableNodes.execute()`
   into a separate registry, keyed by target container name.

3. **Include structure**: We wrap `IncludeLaunchDescription.execute()` to record the include
   relationships (which file included which) before delegating to the original implementation.

These are stored in a `DryRunRegistry` instance:

```python
@dataclass
class DryRunRegistry:
    """Accumulates entities during a dry-run execution."""
    process_actions: list[ExecuteLocal]
    composable_nodes: dict[str, list[ComposableNodeRecord]]
    includes: list[IncludeRecord]

    # Source file tracking — maps each collected entity to the launch file it came from.
    # Maintained via a stack pushed/popped by the IncludeLaunchDescription wrapper.
    _source_file_stack: list[Path]
    entity_source_files: dict[int, Path]  # id(entity) -> source file path
```

### Source File Tracking

Every entity we collect is tagged with the launch file it originated from. The mechanism:

1. The `IncludeLaunchDescription` wrapper pushes the included file path onto
   `registry._source_file_stack` before delegating to the original `execute()`, and
   arranges a pop after the included description's entities have been visited (via an
   `OpaqueFunction` appended to the returned entity list, mirroring how
   `IncludeLaunchDescription` itself restores launch file locals).

2. When the patched `__execute_process` or `LoadComposableNodes.execute` records an entity,
   it also records `registry._source_file_stack[-1]` into `registry.entity_source_files`.

3. Layer 2 reads `entity_source_files` and populates `source_file` on each `NodeInfo` /
   `ComposableNodeInfo`.

This gives downstream tools (visualisers, IDE integrations) a direct mapping from every
node to the launch file that defined it.

### Context Setup

The dry run needs a `LaunchContext` that matches the target environment:

```python
def dry_run(
    launch_file: str | Path,
    *,
    launch_arguments: dict[str, str] | None = None,
    environment: dict[str, str] | None = None,
) -> DryRunResult:
```

- `launch_file`: Path to the launch file (any frontend).
- `launch_arguments`: Launch arguments (equivalent to `key:=value` on the CLI).
- `environment`: If provided, used as the process environment for the `LaunchService`. This
  is how you target a specific workspace — pass the environment you get from sourcing that
  workspace's `setup.bash`. If `None`, inherits the current process environment.

### Execution Flow

```python
def dry_run(...) -> DryRunResult:
    registry = DryRunRegistry()

    # 1. Apply patches (context manager restores originals on exit)
    with _apply_patches(registry):

        # 2. Load the launch description from the file
        launch_description = get_launch_description_from_any_launch_file(launch_file)

        # 3. Create and configure the LaunchService
        ls = LaunchService()
        ls.include_launch_description(launch_description)

        # 4. If launch_arguments provided, prepend SetLaunchConfiguration actions
        #    (or pass via launch_description constructor)

        # 5. Run until idle (all futures complete immediately due to our patch)
        ls.run()

    # 6. Return the registry + any context state needed by Layer 2
    return DryRunResult(registry=registry, context=ls.context)
```

### Error Handling

- **`OpaqueFunction` side effects**: Arbitrary Python callables WILL execute. This is
  necessary for correctness — launch files use `OpaqueFunction` for dynamic configuration.
  We accept this risk since the library operates in dev-tool contexts where launch files are
  trusted.

- **Missing packages / executables**: Since we never actually run `ros2 run` or spawn
  processes, missing executables are not an error. The resolved command line will reference
  them but we don't validate their existence.

- **Substitution failures**: If a required launch argument is not provided, the launch system
  will raise `SubstitutionFailure`. We let this propagate — the caller must provide all
  required arguments (or we can extract declared arguments separately via `--show-args`
  equivalent logic).

### Patch Safety

All patches are applied via a context manager that saves and restores the original
implementations:

```python
@contextmanager
def _apply_patches(registry: DryRunRegistry):
    originals = {
        'execute_process': ExecuteLocal._ExecuteLocal__execute_process,
        'load_composable': LoadComposableNodes.execute,
        'include_ld': IncludeLaunchDescription.execute,
    }
    try:
        ExecuteLocal._ExecuteLocal__execute_process = _make_noop_execute(registry)
        LoadComposableNodes.execute = _make_dry_run_load(registry)
        IncludeLaunchDescription.execute = _make_recording_include(originals['include_ld'], registry)
        yield
    finally:
        ExecuteLocal._ExecuteLocal__execute_process = originals['execute_process']
        LoadComposableNodes.execute = originals['load_composable']
        IncludeLaunchDescription.execute = originals['include_ld']
```


## Layer 2: Entity Extractor (`extractor.py`)

### Purpose

Walk the collected entities from Layer 1 and build a structured `LaunchModel` from their
resolved attributes.

### Data Extraction by Entity Type

#### `Node`

| Field | Source | Notes |
|-------|--------|-------|
| Node name (qualified) | `.node_name` property | `/namespace/name` format. Raises if unset. |
| Node namespace | `.expanded_node_namespace` property | |
| Package | Parse from `.process_description.final_cmd` | `.node_package` is raw substitutions only. The resolved package appears in the command as `ros2 run <package> <executable>` or we can resolve the substitution list ourselves against the context. |
| Executable | Parse from `.process_description.final_cmd` | Same situation as package. |
| Remappings | `.expanded_remapping_rules` property | `list[tuple[str, str]]` of `(src, dst)` |
| Parameter sources | Parse `--params-file` and `-p` args from `.cmd` | See Layer 3. Returns `list[ParamSource]` where each is either a file path or inline `key:=value`. |
| Additional arguments | `.cmd` beyond the core ros2 run args | |

**Package and executable resolution**: The `node_package` and `node_executable` properties
return raw substitution lists, not resolved strings. However, the resolved values are embedded
in `process_description.final_cmd`. For a typical `Node`, the command is:
```
[<prefix...>, ros2_run_path, <package>, <executable>, --ros-args, ...]
```
We can also resolve the substitutions ourselves using `perform_substitutions(context,
node.node_package)` since we have the context from the dry run.

#### `ComposableNodeContainer`

Same as `Node`, plus:

| Field | Source | Notes |
|-------|--------|-------|
| Hosted composable nodes | `registry.composable_nodes[container.node_name]` | Joined by container name |

#### `ComposableNode` (via `LoadComposableNodes`)

These are not `Action` instances — the resolved data comes from the `LoadNode.Request` built
by `get_composable_node_load_request()`, captured in our registry.

| Field | Source (from captured request) | Notes |
|-------|-------------------------------|-------|
| Package | `request.package_name` | Fully resolved string |
| Plugin | `request.plugin_name` | Fully resolved string |
| Node name | `request.node_name` | Fully resolved string |
| Node namespace | `request.node_namespace` | Fully resolved string |
| Remappings | `request.remap_rules` | `list[str]` in `src:=dst` format |
| Parameters | `request.parameters` | `list[rcl_interfaces/Parameter]` — fully evaluated, not file paths |
| Extra arguments | `request.extra_arguments` | `list[rcl_interfaces/Parameter]` |

Note: composable node parameters are **already fully resolved** (files are loaded, dicts are
evaluated) because `LoadComposableNodes` needs to serialize them into the service request.
Layer 3 parameter resolution is not needed for composable nodes.

#### `IncludeLaunchDescription`

| Field | Source | Notes |
|-------|--------|-------|
| Source file path | `.launch_description_source.location` | Path to the included file |
| Launch arguments passed | Recorded in our include wrapper | The `SetLaunchConfiguration` actions prepended by include |

### Extraction Output

The extractor produces a `LaunchModel` (see Data Model below) that represents the full
resolved launch tree.


## Layer 3: Parameter Resolver (`parameters.py`)

### Purpose

For regular `Node` actions, parameters are not loaded in the Python launch system — they are
passed as CLI arguments (`--params-file <path>` and `-p name:=value`) and loaded by the node
process itself. Layer 3 optionally loads and merges these parameter sources to produce a final
parameter dictionary per node.

### Parameter Sources (in order)

A node's `--ros-args` section in `cmd` may contain interleaved:

1. `--params-file <path>` — path to a YAML file (may be a temp file created from an inline
   dict, or a user-specified file path)
2. `-p <name>:=<yaml_value>` — inline parameter assignment

ROS 2 parameter loading semantics: later sources override earlier ones, and `--params-file`
loads parameters namespaced under the **fully qualified node name** within the YAML structure.

### YAML Parameter File Format

```yaml
/**:                    # wildcard — applies to all nodes
  ros__parameters:
    param_a: 1
/my_ns/my_node:         # specific node
  ros__parameters:
    param_b: 2
```

### Resolution Algorithm

Parameter resolution always runs as part of `parse` — there is no opt-out. The resolved
parameters appear in the output alongside the source descriptors.

```python
def resolve_parameters(node_info: NodeInfo) -> dict[str, Any]:
    """
    Merge all parameter sources for a node into a final dict.
    """
    merged = {}
    for source in node_info.parameter_sources:
        if isinstance(source, ParamFileSource):
            params = _load_param_yaml(source.path, node_info.fully_qualified_name)
            merged.update(params)
        elif isinstance(source, InlineParamSource):
            merged[source.name] = source.value
    return merged
```

### Temp File Handling

When a launch file specifies inline parameter dicts, `Node._perform_substitutions()` writes
them to temp files via `_create_params_file_from_dict()`. These temp files exist for the
lifetime of the process. Since our dry run completes quickly, we should load these temp files
in Layer 3 **before** the temp directory is cleaned up — or capture their contents during the
dry run.

Strategy: In the patched `__execute_process`, before calling `__cleanup()`, read any temp
param file contents and stash them in the registry. This way Layer 3 has the data even after
temp files are gone.


## Data Model (`model.py`)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NodeType(Enum):
    """Discriminator for the kind of node."""
    NODE = "node"
    COMPOSABLE_NODE_CONTAINER = "composable_node_container"
    COMPOSABLE_NODE = "composable_node"


@dataclass
class ParamFileSource:
    """A parameter source from a YAML file."""
    path: Path
    contents: dict[str, Any] | None = None  # Pre-loaded if available (e.g. temp files)


@dataclass
class InlineParamSource:
    """A parameter source from a -p name:=value argument."""
    name: str
    value: Any  # Parsed from YAML scalar


ParamSource = ParamFileSource | InlineParamSource


@dataclass
class NodeInfo:
    """Resolved information about a regular (process-based) node."""
    node_type: NodeType
    package: str
    executable: str
    name: str | None                            # Bare node name (may be None if unspecified)
    namespace: str                              # Resolved namespace
    fully_qualified_name: str | None            # /namespace/name (None if name unspecified)
    parameter_sources: list[ParamSource]        # Ordered parameter sources from cmd
    parameters: dict[str, Any] | None = None    # Merged parameters (filled by Layer 3)
    remappings: list[tuple[str, str]] = field(default_factory=list)
    additional_args: list[str] = field(default_factory=list)
    cmd: list[str] = field(default_factory=list)  # Full resolved command line
    source_file: Path | None = None             # Launch file this node was defined in


@dataclass
class ComposableNodeInfo:
    """Resolved information about a composable (in-process) node."""
    node_type: NodeType = field(default=NodeType.COMPOSABLE_NODE, init=False)
    package: str = ""
    plugin: str = ""                            # Plugin class identifier
    name: str | None = None
    namespace: str = ""
    fully_qualified_name: str | None = None     # /namespace/name (None if name unspecified)
    parameters: dict[str, Any] = field(default_factory=dict)  # Already fully resolved
    remappings: list[tuple[str, str]] = field(default_factory=list)
    extra_arguments: dict[str, Any] = field(default_factory=dict)
    source_file: Path | None = None             # Launch file this node was defined in


@dataclass
class ContainerInfo(NodeInfo):
    """A composable node container — a Node that hosts ComposableNodes."""
    node_type: NodeType = field(default=NodeType.COMPOSABLE_NODE_CONTAINER, init=False)
    composable_nodes: list[ComposableNodeInfo] = field(default_factory=list)


@dataclass
class IncludeInfo:
    """Record of an included launch file."""
    source_file: Path                           # The file that contains the include
    included_file: Path                         # The file being included
    launch_arguments: dict[str, str]            # Arguments passed to the include
    includes: list[IncludeInfo] = field(default_factory=list)  # Nested includes (recursive)


@dataclass
class LaunchModel:
    """
    The complete resolved representation of a launch file execution.

    This is the top-level output of the library.
    """
    launch_file: Path                           # The root launch file
    launch_arguments: dict[str, str]            # Arguments provided for this dry run

    # Flat list of all nodes (easy to iterate)
    nodes: list[NodeInfo | ContainerInfo] = field(default_factory=list)

    # Include tree (preserves structure)
    includes: list[IncludeInfo] = field(default_factory=list)

    # All declared launch arguments (name -> default value or None)
    declared_arguments: dict[str, str | None] = field(default_factory=dict)
```


## Serialisation

The `LaunchModel` must be serialisable to JSON for the TypeScript interface. We provide:

```python
def to_dict(model: LaunchModel) -> dict:
    """Convert a LaunchModel to a JSON-serialisable dict."""
    ...

def to_json(model: LaunchModel, **kwargs) -> str:
    """Serialise a LaunchModel to a JSON string."""
    ...
```

Enum values are serialised as their string values. `Path` objects are serialised as strings.
`ParamSource` variants use a `{"type": "file", ...}` / `{"type": "inline", ...}`
discriminator.


## Public API

### CLI (primary interface)

The CLI is the primary interface, designed to be called from TypeScript (via subprocess + JSON)
and other languages. All commands output JSON to stdout.

```
launch_interface parse <launch_file> [key:=value ...]
launch_interface args <launch_file>
```

#### `launch_interface parse`

Performs a full dry-run execution of the launch file, resolves all substitutions, conditionals,
includes, and scoping, and outputs the complete resolved launch graph as JSON. Parameters are
always fully resolved (YAML files loaded and merged).

Launch arguments are passed as `key:=value` pairs, matching the `ros2 launch` convention.

```bash
launch_interface parse path/to/my_launch.py robot_name:=atlas use_sim:=true
```

#### `launch_interface args`

Lists the declared launch arguments for a launch file without performing a full dry run.
Wraps the same logic as `ros2 launch --show-args`.

```bash
launch_interface args path/to/my_launch.py
```

### Python (internal)

The Python API exists to implement the CLI — it is not a public interface for external Python
consumers. The internal structure is documented in the architecture sections below, but the
CLI JSON output is the only stable contract.


## Testing

### Strategy

Tests require a sourced ROS 2 installation — the library only works in a ROS environment and
we test as we play. No mocking of the ROS package index or workspace infrastructure.

### Test Workspace

A self-contained test workspace lives inside the repo at `test/test_ws/`. It contains minimal
ROS packages with dummy nodes that exist solely to give the launch system real packages and
executables to resolve against.

```
launch_interface/
  launch_interface/
    __init__.py
    ...
  test/
    conftest.py                  # session fixture: builds test_ws, sources it
    test_parse.py
    test_args.py
    test_ws/
      COLCON_IGNORE              # outer workspace builds skip this
      .gitignore                 # ignores build/ install/ log/
      src/
        test_nodes/
          package.xml
          setup.py
          test_nodes/
            node_a.py
            ...
      launch_files/
        simple_node.launch.py
        ...
      params/
        test_params.yaml
```

- **`COLCON_IGNORE`**: Prevents `colcon build` at the outer workspace level from descending
  into the test workspace.
- **`.gitignore`**: Excludes `build/`, `install/`, and `log/` directories from version control.
- **`conftest.py`**: A session-scoped pytest fixture builds the test workspace once
  (`colcon build` inside `test/test_ws/`), sources `test/test_ws/install/setup.bash`, and
  configures the environment for all tests in the session.

### Test Cases

Tests call `launch_interface parse` (via subprocess or the Python API) against launch files in
the test workspace and assert the JSON output matches expected structure.

Test matrix:

| # | Test file | Exercises |
|---|-----------|-----------|
| 1 | Simple single node (Python) | Basic `Node()`, name, namespace, package, executable |
| 2 | Node with parameters (Python) | `--params-file`, inline `-p`, parameter merging |
| 3 | Remappings and arguments (Python) | `DeclareLaunchArgument`, `LaunchConfiguration`, remappings |
| 4 | Include chain (Python→Python) | `IncludeLaunchDescription`, source file tracking, arg passing |
| 5 | Composable nodes (Python) | `ComposableNodeContainer` + `LoadComposableNodes` |
| 6 | Conditional nodes (Python) | `IfCondition`/`UnlessCondition` — some nodes present, some not |
| 7 | XML launch file | Same as #1 but XML frontend |
| 8 | YAML launch file | Same as #1 but YAML frontend |
| 9 | Namespace scoping via `GroupAction` | `PushRosNamespace` inside group |


## Dependencies

- `launch` (ROS 2 launch core)
- `launch_ros` (ROS 2 launch extensions for nodes, composable nodes, etc.)
- `launch_xml` (XML frontend — optional, only if XML launch files are used)
- `launch_yaml` (YAML frontend — optional, only if YAML launch files are used)
- `composition_interfaces` (for `LoadNode.Request` type used in composable node extraction)

The library must be used in an environment where these packages are available (i.e., a sourced
ROS 2 workspace).


## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Name mangling fragility**: `_ExecuteLocal__execute_process` could be renamed upstream | Pin to tested ROS 2 distributions. Add a startup check that the attribute exists. |
| **OpaqueFunction side effects**: Arbitrary Python runs during dry run | Document that launch files must be trusted. This is inherent to the approach. |
| **`CommandSubstitution` side effects**: `$(command ...)` in XML/YAML executes a real subprocess during substitution resolution | Unavoidable — we need the output for correct resolution. Same behaviour as `ros2 launch` itself. |
| **`PythonExpression` side effects**: `$(eval ...)` calls `eval()` on arbitrary Python during substitution resolution | Same as above — unavoidable and matches real launch behaviour. |
| **Temp file lifetime**: Inline param dicts written to temp files may be cleaned up | Capture temp file contents in the patched execute before cleanup. |
| **Incomplete composable node data**: `LoadComposableNodes` requires `composition_interfaces` types | This is a standard ROS 2 package, always available. |
| **Launch arguments not provided**: Substitution resolution fails | Provide `get_launch_arguments()` so callers can discover required args first. |
| **Python launch files with import-time side effects** | Out of scope — same risk as `ros2 launch` itself. |
| **Event handlers that depend on process lifecycle** (e.g. `OnProcessExit` triggers) | These handlers will fire with our synthetic completion. Nodes launched by `OnProcessExit` callbacks will still be captured. Need to verify this works correctly. |
| **`TimerAction`-gated nodes**: Nodes launched after a delay will not be captured | Out of scope for initial implementation. The dry run completes as soon as all futures resolve (immediately), so timer-delayed actions never fire. |


## Future Considerations

- **Write support**: Generating / modifying launch files. Likely template-based for XML/YAML,
  AST manipulation (`libcst` or `ast`) for Python launch files. Separate design.

- **TypeScript interface**: Subprocess + JSON is the initial approach. Could explore tighter
  integration via PyO3 + NASM/WASM or a persistent language server protocol if performance
  matters.

- **Caching**: Dry-run results could be cached keyed on (launch file mtime, arguments,
  environment hash) for faster repeated queries in IDE tooling.

- **Incremental resolution**: For large launch graphs, resolving only a subtree that changed.

- **Parameter file watching**: In IDE tooling, watching referenced YAML parameter files for
  changes and re-resolving.
