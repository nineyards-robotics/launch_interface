"""Validate that all expected JSON files conform to their schemas."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).resolve().parent.parent / 'schema'
EXPECTED_DIR = Path(__file__).parent / 'expected'

PARSE_SCHEMA = json.loads((SCHEMA_DIR / 'parse.schema.json').read_text())
ARGS_SCHEMA = json.loads((SCHEMA_DIR / 'args.schema.json').read_text())


def _parse_expected_files():
    return sorted(EXPECTED_DIR.glob('parse_*.json'))


def _args_expected_files():
    return sorted(EXPECTED_DIR.glob('args_*.json'))


@pytest.mark.parametrize(
    'expected_file',
    _parse_expected_files(),
    ids=lambda p: p.name,
)
def test_parse_expected_matches_schema(expected_file):
    data = json.loads(expected_file.read_text())
    jsonschema.validate(data, PARSE_SCHEMA)


@pytest.mark.parametrize(
    'expected_file',
    _args_expected_files(),
    ids=lambda p: p.name,
)
def test_args_expected_matches_schema(expected_file):
    data = json.loads(expected_file.read_text())
    jsonschema.validate(data, ARGS_SCHEMA)
