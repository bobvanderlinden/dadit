from tree_sitter import Node
from typing import Iterable
import re
from ..json import JSON, dumps as json_dumps
from ..tree_sitter.selector import (
    Selector,
    query,
    chain,
    children,
    conditional,
    type,
    field,
    union,
    parent,
    filter,
    single,
    optional,
    previous_node,
)
from ..tree_sitter.document import Document
from ..tree_sitter.edit import Edit, Replace, Insert, Remove, apply_edits
from ..json_patch import (
    JSONPatchOperation,
    JSONPatchAdd,
    JSONPatchRemove,
    JSONPatchReplace,
    JSONPatchMove,
    JSONPatchCopy,
    JSONPatchTest,
    TestFailure,
)
from .parse import parse_node

default_indentation = "  "


def key_field(str) -> Selector:
    return filter(
        chain(
            field("key"),
            type("flow_node"),
            children,
            conditional(lambda node: parse_node(node) == str),
        )
    )


def get_indentation(node: Node) -> str:
    start_byte = node.start_byte
    while not b"\n" in node.text[: start_byte - node.start_byte]:
        if node.parent:
            node = node.parent
        else:
            break
    prefix = node.text[: start_byte - node.start_byte]
    prefix = prefix.decode("utf-8")
    if match := re.search("(?:^|\n)([ \t]*)([^ \t\n\r][^\n]*)?$", prefix):
        return match.group(1)
    return ""


def get_block_indentation(node: Node) -> str:
    start_byte = node.start_byte
    while not b"\n" in node.text[: start_byte - node.start_byte]:
        if node.parent:
            node = node.parent
        else:
            break
    prefix = node.text[: start_byte - node.start_byte]
    prefix = prefix.decode("utf-8")
    if match := re.search("(?:^|\n)([ \t]*)([^ \t\n\r][^\n]*)?$", prefix):
        match match.groups():
            case [indentation, None]:
                return indentation
            case [indentation, rest] if rest[0] == "-":
                return indentation + default_indentation
            case [indentation, rest]:
                return indentation
            case _:
                raise ValueError(f"Invalid indentation {match}")
    return ""


def indent(text: str, indentation: str = default_indentation) -> str:
    return "\n".join([f"{indentation}{line}" for line in text.splitlines()])


def get_text_before(child: Node) -> bytes:
    parent = child
    while parent.parent and parent.start_byte == child.start_byte:
        parent = parent.parent
    return parent.text[: child.start_byte - parent.start_byte]


def get_text_after(child: Node) -> bytes:
    parent = child
    while parent.parent and parent.end_byte == child.end_byte:
        parent = parent.parent
    return parent.text[child.end_byte - parent.start_byte :]


comment = conditional(lambda node: node.type == "comment")


def converge(node: Node) -> Node:
    match node.type:
        case "stream" | "document" | "block_node" | "flow_node" | "plain_scalar":
            return converge(
                single(
                    (
                        child
                        for child in node.children
                        if child.type not in {"comment", "anchor"}
                    )
                )
            )
        case _:
            return node


def get_node_by_name(node: Node, name: str) -> Node:
    node = converge(node)
    match node.type:
        case "document":
            return get_node_by_name(
                single(
                    query(
                        node,
                        children,
                        union(
                            type("block_node"),
                            type("flow_node"),
                        ),
                    )
                ),
                name,
            )
        case "block_node":
            return get_node_by_name(
                single(
                    query(
                        node,
                        children,
                        union(
                            type("block_scalar"),
                            type("block_mapping"),
                            type("block_sequence"),
                        ),
                    )
                ),
                name,
            )
        case "block_mapping":
            return single(
                query(node, children, type("block_mapping_pair"), key_field(name))
            )
        case "block_sequence":
            return [*query(node, children, type("block_sequence_item"))][int(name)]
        case "flow_node":
            return get_node_by_name(
                single(
                    query(
                        node,
                        children,
                        union(
                            type("plain_scalar"),
                            type("flow_sequence"),
                            type("flow_mapping"),
                        ),
                    )
                ),
                name,
            )
        case "block_sequence_item" | "flow_item":
            return get_node_by_name(
                single(
                    query(
                        node,
                        children,
                        union(type("block_node"), type("flow_node")),
                    )
                ),
                name,
            )
        case "block_mapping_pair" | "flow_pair":
            return get_node_by_name(single(query(node, field("value"))), name)
        case "flow_sequence":
            raise NotImplemented(f"flow_sequence not implemented")
        case "flow_mapping":
            raise NotImplemented(f"flow_sequence not implemented")
        case _:
            raise ValueError(f"Cannot navigate in {node.type}")


def get_node_by_path(node: Node, path: list[str]) -> Node:
    if node.type == "stream" and (child := node.named_child(0)):
        node = child
    match path:
        case []:
            return node
        case [segment]:
            return get_node_by_name(node, segment)
        case [segment, *rest]:
            return get_node_by_path(get_node_by_name(node, segment), rest)
        case _:
            raise ValueError(f"Invalid path {path}")


type Selection = tuple[int, int]


def select_node(node: Node) -> Selection:
    return node.start_byte, node.end_byte


def expand_prefix_pattern(node: Node, selection: Selection, pattern: str) -> Selection:
    prefix = get_text_before(node).decode("utf-8")
    if match := re.search(pattern, prefix):
        start, end = selection
        match_length = len(match.group(0).encode("utf-8"))
        return start - match_length, end
    return selection


def expand_suffix_pattern(node: Node, selection: Selection, pattern: str) -> Selection:
    suffix = get_text_after(node).decode("utf-8")
    if match := re.search(pattern, suffix):
        start, end = selection
        match_length = len(match.group(0).encode("utf-8"))
        return start, end + match_length
    return selection


def row_of(node: Node) -> int:
    return node.start_point[0]


def edit_replace(root: Node, path: list[str], value: JSON) -> Iterable[Edit]:
    node = get_node_by_path(root, path)
    match node.type:
        case "block_mapping_pair":
            selection = select_node(node)
            key_node = node.child_by_field_name("key")
            assert key_node
            key = key_node.text.decode("utf-8")
            yaml_pair = indent_block(
                stringify_block_mapping_pair(key, value),
                indentation=get_block_indentation(node),
            )

            comment = None

            # Find comment from block_scalar.
            if comment_node := optional(
                query(
                    node,
                    children,
                    type("block_scalar"),
                    children,
                    type("comment"),
                )
            ):
                comment = comment_node.text.decode("utf-8")

            # Find adjacent comment from same line.
            if comment_node := node.next_sibling:
                if comment_node.type == "comment" and row_of(comment_node) == row_of(
                    node
                ):
                    comment = comment_node.text.decode("utf-8")
                    # Replace this comment with the pair.
                    selection = (selection[0], comment_node.end_byte)

            if comment:
                yaml_pair = re.sub(r"(\n|$)", f" {comment}\\1", yaml_pair, count=1)

            if node.text.endswith(b"\n"):
                yaml_pair += "\n"
            yaml_pair = yaml_pair.encode("utf-8")
            yield Replace(*selection, yaml_pair)
        case "flow_pair":
            yaml_value = stringify_flow(value).encode("utf-8")
            yield Replace(node.start_byte, node.end_byte, yaml_value)
        case "block_sequence_item":
            indentation = get_block_indentation(node)
            yaml_value = indent_block(
                stringify_block_sequence_item(value), indentation=indentation
            )
            if node.text.endswith(b"\n"):
                yaml_value += "\n"
            selection = select_node(node)
            selection = expand_suffix_pattern(node, selection, r"^[ \t]+")
            yield Replace(selection[0], selection[1], yaml_value.encode("utf-8"))
        case "document":
            yaml_value = stringify_block(value) + "\n"
            yield Replace(node.start_byte, node.end_byte, yaml_value.encode("utf-8"))
        case _:
            raise ValueError(f"Invalid node type {node.type}")


def edit_add(root: Node, path: list[str], value: JSON) -> Iterable[Edit]:
    *parent_path, key = path
    parent = get_node_by_path(root, parent_path)
    parent = single(
        query(
            parent,
            children,
            union(
                chain(
                    type("block_node"),
                    children,
                    union(type("block_sequence"), type("block_mapping")),
                ),
                chain(
                    type("flow_node"),
                    children,
                    union(type("flow_sequence"), type("flow_mapping")),
                ),
            ),
        )
    )
    match parent.type:
        case "block_mapping":
            yaml_fragment = stringify_block_mapping_pair(key, value)
            yield Insert(
                parent.end_byte,
                (
                    indent(
                        yaml_fragment,
                        indentation=get_block_indentation(parent),
                    )
                    + "\n"
                ).encode("utf-8"),
            )
        case "block_sequence":
            siblings = [*query(parent, children, type("block_sequence_item"))]
            index = len(siblings) if key == "-" else int(key)
            yaml_fragment = stringify_block_sequence_item(value)
            if index == len(siblings):
                yield Insert(
                    parent.end_byte,
                    (
                        indent(yaml_fragment, indentation=get_block_indentation(parent))
                        + "\n"
                    ).encode("utf-8"),
                )
            else:
                sibling = siblings[index]
                yield Insert(
                    sibling.start_byte,
                    (
                        indent_block(yaml_fragment, get_indentation(sibling))
                        + "\n"
                        + get_indentation(sibling)
                    ).encode("utf-8"),
                )
        case "flow_mapping":
            yield Insert(
                parent.end_byte,
                (f", {stringify_flow(key)}: {stringify_flow(value)}").encode("utf-8"),
            )
        case "flow_sequence":
            index = int(key)
            siblings = [*query(parent, children, type("flow_sequence_item"))]
            insert_byte, prefix = (
                (siblings[index].end_byte, b", ")
                if index > 0
                else (parent.start_byte + 1, b"")
            )
            yield Insert(
                insert_byte,
                prefix + stringify_flow(value).encode("utf-8"),
            )
        case _:
            raise ValueError(f"Invalid node type {parent.type}")


def edit_remove(root: Node, path: list[str]) -> Iterable[Edit]:
    node = get_node_by_path(root, path)
    match node.type:
        case "block_mapping_pair":
            if node.parent and query(
                node.parent,
                type("block_mapping"),
                children,
                type("block_mapping_pair"),
            ) == [node]:
                yaml_fragment = b"{}"

                selection = select_node(node.parent)
                selection = expand_prefix_pattern(node, selection, r"[ \t]*\n?[ \t]*$")
                selection = expand_suffix_pattern(node, selection, r"^[ \t]+")

                # Make sure we place `{}` before any comment in the parent.
                if comment_node := optional(
                    query(node, previous_node, type("comment"))
                ):
                    yaml_fragment += b" " + comment_node.text
                    selection = (comment_node.start_byte, selection[1])

                # If the block_mapping resides inside an item/pair (ends with `-` or `:`), add a space.
                if (
                    query(
                        node.parent,
                        type("block_mapping"),
                        parent,
                        type("block_node"),
                        parent,
                        union(type("block_sequence_item"), type("block_mapping_pair")),
                    )
                    != []
                ):
                    yaml_fragment = b" " + yaml_fragment

                # If the previous block ended with a newline, let the new expression also end with a newline.
                if node.parent and node.parent.text.endswith(b"\n"):
                    yaml_fragment += b"\n"

                yield Replace(*selection, yaml_fragment)
            else:
                yield Remove(node.start_byte, node.end_byte)
        case "block_sequence_item":
            if query(
                node,
                parent,
                type("block_sequence"),
                children,
                type("block_sequence_item"),
            ) == [node]:
                selection = select_node(node)
                selection = expand_prefix_pattern(node, selection, r"[ \t]*\n[ \t]*$")
                selection = expand_suffix_pattern(node, selection, r"^[ \t]*")

                yaml_fragment = b"[]"

                # Make sure we place `[]` before any comment in the parent.
                if comment_node := optional(
                    query(node, previous_node, type("comment"))
                ):
                    yaml_fragment += b" " + comment_node.text
                    selection = (comment_node.start_byte, selection[1])

                # If the block_sequence resides inside an item/pair (ends with `-` or `:`), add a space.
                if (
                    query(
                        node,
                        parent,
                        type("block_sequence"),
                        parent,
                        type("block_node"),
                        parent,
                        union(type("block_sequence_item"), type("block_mapping_pair")),
                    )
                    != []
                ):
                    yaml_fragment = b" " + yaml_fragment

                # If the previous block ended with a newline, let the new expression also end with a newline.
                if node.text.endswith(b"\n"):
                    yaml_fragment += b"\n"

                yield Replace(*selection, yaml_fragment)
            else:
                selection = select_node(node)
                selection = expand_prefix_pattern(node, selection, r"[ \t]*\n[ \t]*$")
                yield Remove(*selection)
        case "flow_pair":
            yield Remove(node.start_byte, node.end_byte)
        case _:
            raise ValueError(f"Invalid node type {node.type}")


def get_value_by_path(root: JSON, path: list[str]) -> JSON:
    match root, path:
        case _, []:
            return root
        case dict(node), [segment]:
            return node[segment]
        case list(node), [segment]:
            return node[int(segment)]
        case _, [segment, *rest]:
            return get_value_by_path(get_value_by_path(root, [segment]), rest)
        case _, _:
            raise ValueError(f"Invalid path {path}")


def edit_move(root: Node, from_: list[str], path: list[str]) -> Iterable[Edit]:
    root_value = parse_node(root)
    value = get_value_by_path(root_value, path)
    yield from edit_remove(root, path)
    yield from edit_add(root, path, value)


def edit_copy(root: Node, from_: list[str], path: list[str]) -> Iterable[Edit]:
    root_value = parse_node(root)
    value = get_value_by_path(root_value, path)
    yield from edit_add(root, path, value)


def edit_test(root: Node, path: list[str], value: JSON) -> Iterable[Edit]:
    try:
        node = get_node_by_path(root, path)
    except ValueError:
        raise TestFailure(JSONPatchTest(path, value), path)
    match node.type:
        case "block_mapping_pair" | "flow_mapping_pair":
            node = node.child_by_field_name("value")

    if parse_node(node) != value:
        raise TestFailure(JSONPatchTest(path, value), path)


def edit_patch_operation(root: Node, operation: JSONPatchOperation) -> Iterable[Edit]:
    match operation:
        case JSONPatchAdd(path, value):
            yield from edit_add(root, path.parts, value)
        case JSONPatchRemove(path):
            yield from edit_remove(root, path.parts)
        case JSONPatchReplace(path, value):
            yield from edit_replace(root, path.parts, value)
        case JSONPatchMove(from_, path):
            yield from edit_move(root, from_.parts, path.parts)
        case JSONPatchCopy(from_, path):
            yield from edit_copy(root, from_.parts, path.parts)
        case JSONPatchTest(path, value):
            yield from edit_test(root, path.parts, value)
        case _:
            raise ValueError(f"Unsupported JSON patch operation {operation}")


def edit_patch(
    root: Node, patch_operations: Iterable[JSONPatchOperation]
) -> Iterable[Edit]:
    for operation in patch_operations:
        yield from edit_patch_operation(root, operation)


def apply_patch(content: str, patch_operations: Iterable[JSONPatchOperation]) -> str:
    document = Document.parse(content, language="yaml")
    edits = edit_patch(document.tree.root_node, patch_operations)
    document = apply_edits(document, edits)
    return document.text.decode("utf-8")


def stringify_block(value: JSON) -> str:
    match value:
        case list() as value:
            return "\n".join(stringify_block_sequence_item(item) for item in value)
        case dict() as value:
            return "\n".join(
                stringify_block_mapping_pair(key, item) for key, item in value.items()
            )
        case _:
            return stringify_flow(value)


def stringify_flow(value: JSON) -> str:
    return json_dumps(value)


def indent_block(value: str, indentation: str = default_indentation) -> str:
    return f"\n{indentation}".join(value.splitlines())


def stringify_block_sequence_item(value: JSON) -> str:
    match value:
        case list() as value:
            return f"- {indent_block(stringify_block(value))}"
        case dict() as value:
            return f"- {indent_block(stringify_block(value))}"
        case str() as value if value[-1] == "\n":
            return f"- |\n{indent(value)}"
        case str() as value if "\n" in value:
            return f"- |-\n{indent(value)}"
        case str() as value if '"' in value:
            return f"- {stringify_flow(value)}"
        case str() as value:
            return f"- {value}"
        case None:
            return f"- "
        case _:
            return f"- {stringify_block(value)}"


def stringify_block_mapping_pair(key: str, value: JSON) -> str:
    match value:
        case list() as value:
            return f"{key}:\n{stringify_block(value)}"
        case dict() as value:
            return f"{key}:\n{indent(stringify_block(value))}"
        case str() as value if value[-1] == "\n":
            return f"{key}: |\n{indent(value)}"
        case str() as value if "\n" in value:
            return f"{key}: |-\n{indent(value)}"
        case str() as value if '"' in value:
            return f"{key}: {stringify_flow(value)}"
        case str() as value:
            return f"{key}: {value}"
        case None:
            return f"{key}:"
        case _:
            return f"{key}: {stringify_block(value)}"
