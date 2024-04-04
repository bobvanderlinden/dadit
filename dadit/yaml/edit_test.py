from .edit import apply_patch, JSONPatchOperation
import pytest
import jsonpatch
from ruamel.yaml import YAML, Dumper
from io import StringIO
from ..json import JSON


def str_representer(dumper: Dumper, value: str):
    style = None
    if "\n" in value:  # check for multiline string
        style = "|"
    return dumper.represent_scalar(
        tag="tag:yaml.org,2002:str", value=value, style=style
    )


_yaml = YAML()
_yaml.representer.add_representer(str, str_representer)


def dumps(data: JSON) -> str:
    with StringIO() as stream:
        _yaml.dump(data, stream)
        return stream.getvalue()


def assert_patch(source, patch, expected):
    patch = [JSONPatchOperation.from_json(op) for op in patch]
    actual = apply_patch(source, patch)
    assert (
        actual == expected
    ), f"Assertion failed:\nSource:\n{source}\n\nPatch:\n{patch}\n\nExpected:\n{expected}\n\nGot:\n{actual}"


values = [1, "single line", "multi\nline\n", {"a": 1}, ["a", 1], None]
sources = [
    variation
    for value in values
    for variation in [
        ("/a", {"a": value}),
        ("/a/b", {"a": {"b": value}}),
        ("/a/0", {"a": [value]}),
        ("/0/a", [{"a": value}]),
        ("/a/a/a", {"a": {"a": {"a": value}}}),
        ("/a/a/1", {"a": {"a": [value, value, value]}}),
    ]
]


@pytest.mark.parametrize("value", values)
@pytest.mark.parametrize("path,root", sources)
def test_apply_replace_basic(value, path, root):
    source = dumps(root)
    patch = [{"op": "replace", "path": path, "value": value}]
    expected = dumps(jsonpatch.apply_patch(root, patch))
    assert_patch(source, patch, expected)


@pytest.mark.parametrize("path,root", sources)
def test_apply_remove_basic(path, root):
    source = dumps(root)
    patch = [{"op": "remove", "path": path}]
    expected = dumps(jsonpatch.apply_patch(root, patch))
    assert_patch(source, patch, expected)


@pytest.mark.parametrize("value", values)
@pytest.mark.parametrize(
    "path,root",
    [
        variation
        for value in values
        for variation in [
            ("/b", {"a": value}),
            ("/a/c", {"a": {"b": value}}),
            ("/a/0", {"a": [value]}),
            ("/a/1", {"a": [value]}),
            ("/0/b", [{"a": value}]),
            ("/1", [{"a": value}]),
            ("/a/b", {"a": {"a": {"a": value}}}),
        ]
    ],
)
def test_apply_add_basic(value, path, root):
    source = dumps(root)
    patch = [{"op": "add", "path": path, "value": value}]
    expected = dumps(jsonpatch.apply_patch(root, patch))
    print("expected", expected)
    assert_patch(source, patch, expected)
