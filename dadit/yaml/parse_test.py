import pytest
from .parse import parse_node
from ..tree_sitter.document import Document
from ruamel.yaml import YAML
from textwrap import dedent

yaml = YAML()


@pytest.mark.parametrize(
    "input",
    [
        "null",
        "true",
        "false",
        "0",
        "1",
        "-1",
        "0.0",
        "1.0",
        "-1.0",
        "''",
        '""',
        "{}",
        "[]",
        """
        key: value
        """,
        """
        - item
        """,
        """
        {"key": "value"}
        """,
        """
        ["value"]
        """,
        """
        key: |
            multiple
            lines
        """,
        """
        key: |-
            multiple
            lines
        """,
        """
        key: >
            multiple
            lines
        """,
        """
        key: >-
            multiple
            lines
        """,
    ],
)
def test_parse_node(input: str):
    input = dedent(input.removeprefix("\n").removesuffix("\n"))
    document = Document.parse(input, "yaml")
    expected = yaml.load(input)
    actual = parse_node(document.tree.root_node)
    assert actual == expected
