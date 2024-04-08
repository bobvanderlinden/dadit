import sys
import argparse
from typing import Any, IO, Callable, List, Sequence
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
    JSONPatchTest,
)

patchers = {
    "yaml": apply_yaml_patch,
}


def parse_json_patch(path: str) -> list[JSONPatchOperation]:
    with open(path) as file:
        return [JSONPatchOperation.from_json(op) for op in json.load(file)]


def parse_json_pointer(pointer: str) -> JSONPointer:
    return JSONPointer.parse(pointer)


value_parsers = {
    "string": str,
    "int": int,
    "float": float,
    "bool": bool,
    "json": json_loads,
}


def parse_value(value: str) -> JSON:
    for prefix, parser in value_parsers.items():
        if value.startswith(prefix + ":"):
            return parser(value[len(prefix) + 1 :])
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
    **kwargs,
):
    if not format:
        raise ValueError("Could not determine format. Use --format FORMAT to specify.")
    if format not in patchers:
        raise ValueError(f"Unsupported format {format}")
    apply_patch = patchers[format]
    source_content = source.read()
    destination_content = apply_patch(source_content, patch_operations)
    destination.write(destination_content)


def create_patch_action(arg_parser: Callable[[list[str]], List[JSONPatchOperation]]):
    class PatchAction(argparse.Action):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            if not isinstance(values, list):
                raise ValueError(f"Unsupported argument type {type(values)}")
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
    parser = subparsers.add_parser(
        "patch",
        help="transform structured source using JSON patch operations.\nLoads JSON patch operations from a file using --patch-file or specify individual operations using --add, --remove, --replace, --move, --copy.\nJSON paths use / as separator and start with /.\nValues are JSON, unless a prefix is used (string:, int:, float:, bool:).",
    )
    parser.set_defaults(subcommand=patch)
    parser.add_argument(
        "--format", choices=patchers.keys(), help="the format of the source file"
    )

    parser.add_argument(
        "--patch-file",
        metavar="patch_file",
        help="path to JSON file to apply",
        action=create_patch_action(parse_json_patch),
    )

    def parse_replace_args(values) -> List[JSONPatchOperation]:
        pointer, value = tuple_parser([parse_json_pointer, parse_value])(values)
        return [JSONPatchReplace(pointer, value)]

    parser.add_argument(
        "--replace",
        nargs=2,
        metavar=("path", "value"),
        help="replace value at path with new value",
        action=create_patch_action(parse_replace_args),
    )

    def parse_add_args(values) -> List[JSONPatchOperation]:
        pointer, value = tuple_parser([parse_json_pointer, parse_value])(values)
        return [JSONPatchAdd(pointer, value)]

    parser.add_argument(
        "--add",
        nargs=2,
        metavar=("path", "value"),
        help="add new value at path",
        action=create_patch_action(parse_add_args),
    )

    def parse_remove_args(values) -> List[JSONPatchOperation]:
        assert len(values) == 1
        pointer = parse_json_pointer(values[0])
        return [JSONPatchRemove(pointer)]

    parser.add_argument(
        "--remove",
        nargs=1,
        metavar="path",
        help="remove value at path",
        action=create_patch_action(parse_remove_args),
    )

    def parse_move_args(values) -> List[JSONPatchOperation]:
        from_, pointer = tuple_parser([parse_json_pointer, parse_json_pointer])(values)
        return [JSONPatchMove(from_, pointer)]

    parser.add_argument(
        "--move",
        nargs=2,
        metavar=("from_path", "to_path"),
        help="move value at from_path to to_path",
        action=create_patch_action(parse_move_args),
    )

    def parse_copy_args(values) -> List[JSONPatchOperation]:
        from_, pointer = tuple_parser([parse_json_pointer, parse_json_pointer])(values)
        return [JSONPatchCopy(from_, pointer)]

    parser.add_argument(
        "--copy",
        nargs=2,
        metavar=("from_path", "to_path"),
        help="copy value at from_path to to_path",
        action=create_patch_action(parse_copy_args),
    )

    def parse_test_args(values) -> List[JSONPatchOperation]:
        pointer, value = tuple_parser([parse_json_pointer, parse_value])(values)
        return [JSONPatchTest(pointer, value)]

    parser.add_argument(
        "--test",
        nargs=2,
        metavar=("path", "value"),
        help="test value at path is equal to value",
        action=create_patch_action(parse_test_args),
    )

    parser.add_argument(
        "source",
        type=argparse.FileType("r"),
        nargs="?",
        default=sys.stdin,
        help="source file to transform. Defaults to stdin.",
    )
    parser.add_argument(
        "destination",
        type=argparse.FileType("w"),
        nargs="?",
        default=sys.stdout,
        help="destination file to write to. Defaults to stdout.",
    )
