"""Session-scoped fixtures for launch_interface tests.

Builds the test workspace once per session and provides an environment
dict that includes the test workspace overlay, so launch files can
resolve test_nodes packages and executables.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TEST_WS = Path(__file__).parent / 'test_ws'
TEST_NODES_PKG = TEST_WS / 'src' / 'test_nodes'
LAUNCH_DIR = TEST_NODES_PKG / 'launch'
EXPECTED_DIR = Path(__file__).parent / 'expected'


@pytest.fixture(scope='session')
def test_ws_env() -> dict[str, str]:
    """Build the test workspace and return an environment with it sourced."""
    install_dir = TEST_WS / 'install'

    # Build only if install doesn't exist or is older than the source
    src_mtime = max(
        f.stat().st_mtime
        for f in (TEST_WS / 'src').rglob('*')
        if f.is_file()
    )
    needs_build = (
        not install_dir.exists()
        or install_dir.stat().st_mtime < src_mtime
    )

    if needs_build:
        subprocess.check_call(
            ['colcon', 'build', '--paths', 'src/test_nodes'],
            cwd=str(TEST_WS),
        )

    # Source the install overlay to get the modified environment
    setup_bash = install_dir / 'setup.bash'
    assert setup_bash.exists(), f'setup.bash not found at {setup_bash}'

    result = subprocess.run(
        ['bash', '-c', f'source {setup_bash} && env -0'],
        capture_output=True,
        text=True,
        check=True,
    )

    env = {}
    for entry in result.stdout.split('\0'):
        if '=' in entry:
            key, _, value = entry.partition('=')
            env[key] = value

    # Provide a known env var for the env_var_substitution test
    env['TEST_NODE_NAME'] = 'env_resolved_node'

    return env


@pytest.fixture(scope='session')
def launch_file_path():
    """Return a helper to get the absolute path to a source launch file."""
    def _get(name: str) -> str:
        path = LAUNCH_DIR / name
        assert path.exists(), f'Launch file not found: {path}'
        return str(path)
    return _get


# ---------------------------------------------------------------------------
# Path normalisation and JSON comparison
# ---------------------------------------------------------------------------

def _normalise_paths(obj, test_ws: str, install: str):
    """Recursively replace absolute test paths with placeholders.

    ``<INSTALL>`` is checked first since it is a subdirectory of ``<TEST_WS>``.
    """
    if isinstance(obj, str):
        obj = obj.replace(install, '<INSTALL>')
        obj = obj.replace(test_ws, '<TEST_WS>')
        return obj
    if isinstance(obj, list):
        return [_normalise_paths(v, test_ws, install) for v in obj]
    if isinstance(obj, dict):
        return {k: _normalise_paths(v, test_ws, install) for k, v in obj.items()}
    return obj


def _check_cmd_fields(actual, expected):
    """Verify ``cmd`` presence in actual matches expected, then strip from both.

    If a node in the expected JSON has a ``cmd`` field, assert that the
    corresponding node in the actual output also has a non-empty ``cmd``
    list.  The ``cmd`` values in expected files serve as documentation only
    — their contents are not compared.

    Returns (actual_stripped, expected_stripped) with ``cmd`` removed.
    """
    if isinstance(actual, dict) and isinstance(expected, dict):
        if 'cmd' in expected:
            assert 'cmd' in actual, 'expected cmd field but none in actual output'
            assert isinstance(actual['cmd'], list) and len(actual['cmd']) > 0, (
                'cmd should be a non-empty list'
            )
        actual_out = {}
        expected_out = {}
        for key in expected:
            if key == 'cmd':
                continue
            a_val = actual.get(key)
            e_val = expected[key]
            a_stripped, e_stripped = _check_cmd_fields(a_val, e_val)
            actual_out[key] = a_stripped
            expected_out[key] = e_stripped
        # Include any keys in actual that aren't in expected (will cause
        # the diff assertion to flag them)
        for key in actual:
            if key != 'cmd' and key not in expected:
                actual_out[key] = actual[key]
        return actual_out, expected_out
    if isinstance(actual, list) and isinstance(expected, list):
        pairs = zip(actual, expected)
        actual_out = []
        expected_out = []
        for a_item, e_item in pairs:
            a_stripped, e_stripped = _check_cmd_fields(a_item, e_item)
            actual_out.append(a_stripped)
            expected_out.append(e_stripped)
        # Append any extra items from actual (length mismatch → diff will catch it)
        actual_out.extend(actual[len(expected):])
        expected_out.extend(expected[len(actual):])
        return actual_out, expected_out
    return actual, expected


@pytest.fixture(scope='session')
def assert_json(test_ws_env):
    """Fixture that returns a function to compare CLI output against expected JSON.

    Usage::

        assert_json(actual_dict, 'parse_simple_node.json')
    """
    test_ws = str(TEST_WS)
    install = str(TEST_WS / 'install')

    def _assert(actual: dict | list, expected_file: str) -> None:
        normalised = _normalise_paths(actual, test_ws, install)

        path = EXPECTED_DIR / expected_file
        assert path.exists(), f'Expected file not found: {path}'
        expected = json.loads(path.read_text())

        normalised, expected = _check_cmd_fields(normalised, expected)

        assert normalised == expected, (
            f'JSON mismatch against {expected_file}:\n'
            f'actual (normalised):\n{json.dumps(normalised, indent=2)}\n\n'
            f'expected:\n{json.dumps(expected, indent=2)}'
        )

    return _assert


# ---------------------------------------------------------------------------
# CLI runner fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def run_parse(test_ws_env):
    """Fixture that returns a function to run ``launch_interface parse``."""
    def _run(launch_file: str, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, '-m', 'launch_interface', 'parse', launch_file, *args],
            capture_output=True,
            text=True,
            env=test_ws_env,
        )
        assert result.returncode == 0, (
            f'launch_interface parse failed:\n'
            f'stdout: {result.stdout}\n'
            f'stderr: {result.stderr}'
        )
        return json.loads(result.stdout)

    return _run


@pytest.fixture(scope='session')
def run_args(test_ws_env):
    """Fixture that returns a function to run ``launch_interface args``."""
    def _run(launch_file: str) -> list[dict]:
        result = subprocess.run(
            [sys.executable, '-m', 'launch_interface', 'args', launch_file],
            capture_output=True,
            text=True,
            env=test_ws_env,
        )
        assert result.returncode == 0, (
            f'launch_interface args failed:\n'
            f'stdout: {result.stdout}\n'
            f'stderr: {result.stderr}'
        )
        return json.loads(result.stdout)

    return _run
