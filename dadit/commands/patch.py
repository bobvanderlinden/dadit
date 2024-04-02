import sys
import argparse
from typing import Any, IO
import json
from ..yaml.edit import apply_patch as apply_yaml_patch
from ..json_patch import JSONPatchOperation, JSONPatch

patchers = {
    "yaml": apply_yaml_patch,
}


def parse_json_patch(path: str) -> list[JSONPatchOperation]:
    with open(path) as file:
        return [JSONPatchOperation.from_json(op) for op in json.load(file)]


def patch(format: str, source: IO[Any], destination: IO[Any], patch: JSONPatch):
    apply_patch = patchers[format]
    source_content = source.read()
    destination_content = apply_patch(source_content, patch)
    destination.write(destination_content)


def subparser(subparsers):
    parser = subparsers.add_parser("patch", help="Apply JSON patch to source")
    parser.set_defaults(subcommand=patch)
    parser.add_argument("--format", choices=patchers.keys())
    parser.add_argument("patch", type=parse_json_patch)
    parser.add_argument(
        "source", type=argparse.FileType("r"), nargs="?", default=sys.stdin
    )
    parser.add_argument(
        "destination", type=argparse.FileType("w"), nargs="?", default=sys.stdout
    )
