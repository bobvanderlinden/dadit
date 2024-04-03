import sys
import argparse
from typing import Any, IO, Callable, List
import json
from ..json import JSON, loads as json_loads
from ..yaml.edit import apply_patch as apply_yaml_patch
from ..json_patch import (
    JSONPatchOperation,
    JSONPatch,
    JSONPatchAdd,
    JSONPointer,
    JSONPatchRemove,
    JSONPatchReplace,
    JSONPatchMove,
    JSONPatchCopy,
)

patchers = {
    "yaml": apply_yaml_patch,
}


def parse_json_patch(path: str) -> list[JSONPatchOperation]:
    with open(path) as file:
        return [JSONPatchOperation.from_json(op) for op in json.load(file)]


def parse_json_pointer(pointer: str) -> str:
    return JSONPointer.parse(pointer)


def parse_value(value: str) -> JSON:
    return json_loads(value)


def tuple_parser(
    parsers: List[Callable[[str], Any]]
) -> Callable[[List[str]], List[Any]]:
    def parse(values: List[str]) -> List[Any]:
        assert len(parsers) == len(values)
        return [parser(value) for parser, value in zip(parsers, values)]

    return parse


def patch(
    format: str,
    source: IO[Any],
    destination: IO[Any],
    patch_operations: JSONPatch,
    **kwargs
):
    apply_patch = patchers[format]
    source_content = source.read()
    destination_content = apply_patch(source_content, patch_operations)
    destination.write(destination_content)


class AddAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        pointer, value = values
        namespace.patch_operations = [
            *namespace.patch_operations,
            JSONPatchAdd(pointer, value),
        ]


def create_patch_action(arg_parser: Callable[[str], List[JSONPatchOperation]]):
    class PatchAction(argparse.Action):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            setattr(
                namespace,
                "patch_operations",
                [
                    *getattr(namespace, "patch_operations", []),
                    *arg_parser(values),
                ],
            )

    return PatchAction


def subparser(subparsers):
    parser = subparsers.add_parser("patch", help="Apply JSON patch to source")
    parser.set_defaults(subcommand=patch)
    parser.add_argument("--format", choices=patchers.keys())

    parser.add_argument("--patch-file", action=create_patch_action(parse_json_patch))

    def parse_replace_args(values):
        pointer, value = tuple_parser([parse_json_pointer, parse_value])(values)
        return [JSONPatchReplace(pointer, value)]

    parser.add_argument(
        "--replace",
        nargs=2,
        action=create_patch_action(parse_replace_args),
    )

    def parse_add_args(values):
        pointer, value = tuple_parser([parse_json_pointer, parse_value])(values)
        return [JSONPatchAdd(pointer, value)]

    parser.add_argument(
        "--add",
        nargs=2,
        action=create_patch_action(parse_add_args),
    )

    def parse_remove_args(values):
        (pointer) = tuple_parser([parse_json_pointer(values)])
        return [JSONPatchRemove(pointer)]

    parser.add_argument(
        "--remove",
        nargs=1,
        action=create_patch_action(parse_remove_args),
    )

    def parse_move_args(values):
        from_, pointer = tuple_parser([parse_json_pointer, parse_json_pointer])(values)
        return [JSONPatchMove(from_, pointer)]

    parser.add_argument(
        "--move",
        nargs=2,
        action=create_patch_action(parse_move_args),
    )

    def parse_copy_args(values):
        from_, pointer = tuple_parser([parse_json_pointer, parse_json_pointer])(values)
        return [JSONPatchCopy(from_, pointer)]

    parser.add_argument(
        "--copy",
        nargs=2,
        action=create_patch_action(parse_copy_args),
    )

    parser.add_argument(
        "source", type=argparse.FileType("r"), nargs="?", default=sys.stdin
    )
    parser.add_argument(
        "destination", type=argparse.FileType("w"), nargs="?", default=sys.stdout
    )
