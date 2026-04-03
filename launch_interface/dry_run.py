"""Layer 1: Dry-run executor.

Runs a launch file through the real LaunchService pipeline, resolving all
substitutions, conditionals, includes, and scoping — but prevents any OS
processes from being spawned or ROS service calls from being made.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from launch import LaunchDescription, LaunchService
from launch.actions import (
    ExecuteLocal,
    IncludeLaunchDescription,
    SetLaunchConfiguration,
)
from launch_ros.actions import LoadComposableNodes


# ---------------------------------------------------------------------------
# Registry — accumulates entities during the dry run
# ---------------------------------------------------------------------------

@dataclass
class ComposableNodeRecord:
    node_description: Any  # ComposableNode description object
    request: Any  # LoadNode.Request (or None if we can't build one)


@dataclass
class IncludeRecord:
    source_file: Path
    included_file: Path
    launch_arguments: dict[str, str]
    children: list[IncludeRecord] = field(default_factory=list)


@dataclass
class DryRunRegistry:
    process_actions: list[ExecuteLocal] = field(default_factory=list)
    composable_nodes: dict[str, list[ComposableNodeRecord]] = field(default_factory=dict)
    includes: list[IncludeRecord] = field(default_factory=list)

    _source_file_stack: list[Path] = field(default_factory=list)
    entity_source_files: dict[int, Path] = field(default_factory=dict)

    # Include stack for building the nested include tree
    _include_stack: list[IncludeRecord] = field(default_factory=list)

    # Stashed temp file contents: id(action) -> {path: contents}
    temp_file_contents: dict[int, dict[str, Any]] = field(default_factory=dict)

    def current_source_file(self) -> Path | None:
        return self._source_file_stack[-1] if self._source_file_stack else None

    def record_process_action(self, action: ExecuteLocal) -> None:
        self.process_actions.append(action)
        src = self.current_source_file()
        if src is not None:
            self.entity_source_files[id(action)] = src

    def record_composable_node(
        self,
        container_name: str,
        node_desc: Any,
        request: Any,
    ) -> None:
        record = ComposableNodeRecord(node_description=node_desc, request=request)
        self.composable_nodes.setdefault(container_name, []).append(record)
        src = self.current_source_file()
        if src is not None:
            self.entity_source_files[id(record)] = src


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

def _stash_temp_param_files(registry: DryRunRegistry, action: ExecuteLocal) -> None:
    """Read any temp parameter files before cleanup destroys them."""
    try:
        cmd = action.process_details.get('cmd') if hasattr(action, 'process_details') and action.process_details else None
        if cmd is None:
            cmd = action.cmd if hasattr(action, 'cmd') else None
        if cmd is None:
            return
        # Look for --params-file args pointing to /tmp
        import tempfile
        tmp_dir = tempfile.gettempdir()
        stashed: dict[str, Any] = {}
        i = 0
        cmd_list = list(cmd) if cmd else []
        while i < len(cmd_list):
            if cmd_list[i] == '--params-file' and i + 1 < len(cmd_list):
                path = cmd_list[i + 1]
                if path.startswith(tmp_dir):
                    try:
                        import yaml
                        with open(path) as f:
                            stashed[path] = yaml.safe_load(f)
                    except Exception:
                        pass
                i += 2
            else:
                i += 1
        if stashed:
            registry.temp_file_contents[id(action)] = stashed
    except Exception:
        pass


def _make_noop_execute(registry: DryRunRegistry):
    """Create a replacement for ExecuteLocal.__execute_process."""
    async def _noop_execute_process(self, context):
        from launch.events.process import ProcessExited

        # Stash temp param file contents before cleanup
        _stash_temp_param_files(registry, self)
        # Record this action — use the source file tagged during execute()
        registry.process_actions.append(self)
        tagged_source = getattr(self, '_dry_run_source_file', None)
        if tagged_source is not None:
            registry.entity_source_files[id(self)] = tagged_source

        # Emit ProcessExited event so OnProcessExit handlers fire.
        # We must supply a fake pid since no real process was spawned.
        process_event_args = self._ExecuteLocal__process_event_args
        if process_event_args is not None:
            event_kwargs = dict(process_event_args)
            event_kwargs.setdefault('pid', 0)
            event_kwargs['returncode'] = 0
            try:
                await context.emit_event(ProcessExited(**event_kwargs))
            except Exception:
                pass

        # Signal completion
        self._ExecuteLocal__cleanup()

    return _noop_execute_process


def _make_tagging_execute(original_execute, registry: DryRunRegistry):
    """Wrap ExecuteLocal.execute to tag source file before async task."""
    def _tagging_execute(self, context):
        # Tag with current source file (stack is correct at this point)
        self._dry_run_source_file = registry.current_source_file()
        return original_execute(self, context)
    return _tagging_execute


def _make_dry_run_load(registry: DryRunRegistry):
    """Create a replacement for LoadComposableNodes.execute."""
    def _dry_run_load_composable_nodes(self, context):
        from launch.utilities import (
            normalize_to_list_of_substitutions,
            perform_substitutions,
        )
        from launch_ros.actions import ComposableNodeContainer
        from launch_ros.actions.load_composable_nodes import (
            get_composable_node_load_request,
            is_a_subclass,
        )

        # Resolve target container name — mirrors original execute() logic
        tc = self._LoadComposableNodes__target_container
        if is_a_subclass(tc, ComposableNodeContainer):
            target = tc.node_name
        else:
            subs = normalize_to_list_of_substitutions(tc)
            target = perform_substitutions(context, subs)

        for node_desc in self._LoadComposableNodes__composable_node_descriptions:
            try:
                request = get_composable_node_load_request(node_desc, context)
            except Exception:
                request = None
            if request is not None:
                registry.record_composable_node(target, node_desc, request)

    return _dry_run_load_composable_nodes


def _make_recording_include(original_execute, registry: DryRunRegistry):
    """Create a replacement for IncludeLaunchDescription.execute."""
    def _recording_include(self, context):
        from launch.utilities import perform_substitutions
        from launch.actions import OpaqueFunction

        # Determine included file path — location is stored as substitution list
        source = self.launch_description_source
        loc_subs = source._LaunchDescriptionSource__location
        if isinstance(loc_subs, list):
            included_path = Path(perform_substitutions(context, loc_subs))
        elif isinstance(loc_subs, str):
            included_path = Path(loc_subs)
        else:
            included_path = Path(str(source.location))

        # Determine the source file that contains this include
        caller = registry.current_source_file()
        if caller is None:
            caller = included_path

        # Collect launch arguments being passed
        launch_args = {}
        for arg_action in self._IncludeLaunchDescription__launch_arguments:
            if isinstance(arg_action, tuple) and len(arg_action) == 2:
                key, value = arg_action
                if hasattr(key, '__iter__') and not isinstance(key, str):
                    key = perform_substitutions(context, key)
                if hasattr(value, '__iter__') and not isinstance(value, str):
                    value = perform_substitutions(context, value)
                launch_args[str(key)] = str(value)

        # Create include record
        record = IncludeRecord(
            source_file=caller,
            included_file=included_path,
            launch_arguments=launch_args,
        )

        # Add to parent or root
        if registry._include_stack:
            registry._include_stack[-1].children.append(record)
        else:
            registry.includes.append(record)

        # Push the included file path BEFORE calling original execute.
        # The original execute returns sub-actions that will be processed
        # later by the launch service. We inject push/pop actions around them.
        registry._source_file_stack.append(included_path)
        registry._include_stack.append(record)

        result = original_execute(self, context)

        # The result is a list of actions. We need to wrap them with
        # push/pop of source file stack. But since original_execute
        # already returned the sub-actions (which will be processed
        # in order by the launch service), we append a pop action.
        registry._source_file_stack.pop()
        registry._include_stack.pop()

        if result is None:
            return result

        # Wrap: push source file, then actions, then pop source file
        def _push_source(ctx):
            registry._source_file_stack.append(included_path)
            registry._include_stack.append(record)

        def _pop_source(ctx):
            registry._source_file_stack.pop()
            registry._include_stack.pop()

        wrapped = [OpaqueFunction(function=_push_source)]
        wrapped.extend(result)
        wrapped.append(OpaqueFunction(function=_pop_source))
        return wrapped

    return _recording_include


# ---------------------------------------------------------------------------
# Patch context manager
# ---------------------------------------------------------------------------

@contextmanager
def _apply_patches(registry: DryRunRegistry):
    originals = {
        'execute_process': ExecuteLocal._ExecuteLocal__execute_process,
        'execute_local_execute': ExecuteLocal.execute,
        'load_composable': LoadComposableNodes.execute,
        'include_ld': IncludeLaunchDescription.execute,
    }
    try:
        ExecuteLocal._ExecuteLocal__execute_process = _make_noop_execute(registry)
        ExecuteLocal.execute = _make_tagging_execute(originals['execute_local_execute'], registry)
        LoadComposableNodes.execute = _make_dry_run_load(registry)
        IncludeLaunchDescription.execute = _make_recording_include(
            originals['include_ld'], registry
        )
        yield
    finally:
        ExecuteLocal._ExecuteLocal__execute_process = originals['execute_process']
        ExecuteLocal.execute = originals['execute_local_execute']
        LoadComposableNodes.execute = originals['load_composable']
        IncludeLaunchDescription.execute = originals['include_ld']


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class DryRunResult:
    registry: DryRunRegistry
    context: Any  # LaunchContext
    launch_description: LaunchDescription


def _load_launch_description(launch_file: Path) -> LaunchDescription:
    """Load a launch description from any frontend (Python, XML, YAML)."""
    name = launch_file.name

    if name.endswith('.launch.py') or name.endswith('.py'):
        from launch.launch_description_sources import PythonLaunchDescriptionSource
        source = PythonLaunchDescriptionSource(str(launch_file))
        return source.try_get_launch_description_without_context()
    elif name.endswith('.launch.xml'):
        from launch.launch_description_sources import FrontendLaunchDescriptionSource
        source = FrontendLaunchDescriptionSource(launch_file_path=str(launch_file))
        return source.try_get_launch_description_without_context()
    elif name.endswith('.launch.yaml') or name.endswith('.launch.yml'):
        from launch.launch_description_sources import FrontendLaunchDescriptionSource
        source = FrontendLaunchDescriptionSource(launch_file_path=str(launch_file))
        return source.try_get_launch_description_without_context()
    else:
        # Fallback: try direct Python import
        import importlib.util
        spec = importlib.util.spec_from_file_location('_launch_file', str(launch_file))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.generate_launch_description()


def dry_run(
    launch_file: str | Path,
    *,
    launch_arguments: dict[str, str] | None = None,
    environment: dict[str, str] | None = None,
) -> DryRunResult:
    """Execute a launch file in dry-run mode."""
    launch_file = Path(launch_file).resolve()
    registry = DryRunRegistry()

    # Push root launch file onto source stack
    registry._source_file_stack.append(launch_file)

    with _apply_patches(registry):
        # Load the launch description using the appropriate frontend parser
        launch_description = _load_launch_description(launch_file)

        # Prepend launch argument overrides
        if launch_arguments:
            arg_actions = [
                SetLaunchConfiguration(name=k, value=v)
                for k, v in launch_arguments.items()
            ]
            launch_description = LaunchDescription(
                arg_actions + list(launch_description.entities)
            )

        # Suppress launch logging to avoid polluting JSON output
        import logging
        launch_logger = logging.getLogger('launch')
        old_level = launch_logger.level
        launch_logger.setLevel(logging.CRITICAL)

        # Create and run the launch service
        ls = LaunchService(noninteractive=True)
        ls.include_launch_description(launch_description)

        if environment is not None:
            import os
            old_env = os.environ.copy()
            os.environ.clear()
            os.environ.update(environment)

        try:
            rc = ls.run()
        finally:
            launch_logger.setLevel(old_level)
            if environment is not None:
                os.environ.clear()
                os.environ.update(old_env)

        if rc != 0:
            raise RuntimeError(
                f'Launch file execution failed with return code {rc}'
            )

    registry._source_file_stack.pop()

    return DryRunResult(
        registry=registry,
        context=ls.context,
        launch_description=launch_description,
    )
