from ..tree_sitter.selector import (
    query,
    children,
    type,
    field,
    single,
)
from tree_sitter import Node
from ..json import JSON
import re


def parse_node(node: Node) -> JSON:
    match node.type:
        case "block_mapping":
            return {
                single(query(pair, field("key"))).text: parse_node(
                    single(query(pair, field("value")))
                )
                for pair in query(node, children, type("block_mapping_pair"))
            }
        case "block_sequence":
            return [
                parse_node(item)
                for item in query(node, children, type("block_sequence_item"))
            ]
        case "flow_mapping":
            return {
                parse_node(pair.child_by_field_name("key")): parse_node(
                    pair.child_by_field_name("value")
                )
                for pair in query(node, children, type("flow_pair"))
            }
        case "flow_sequence":
            return [
                parse_node(item) for item in query(node, children, type("flow_item"))
            ]
        case (
            "document"
            | "stream"
            | "block_node"
            | "flow_node"
            | "flow_scalar"
            | "plain_scalar"
        ):
            return single(query(node, children))
        case "integer_scalar":
            return int(node.text)
        case "float_scalar":
            return float(node.text)
        case "string_scalar":
            return node.text.decode("utf-8")
        case "double_quote_scalar":
            return unescape_double_quoted(node.text.decode("utf-8")[1:-1])
        case "single_quote_scalar":
            return unescape_single_quoted(node.text.decode("utf-8")[1:-1])
        case "block_scalar":
            text = node.text.decode("utf-8")
            match = re.search(r"^([\\|>]-?)[^\\n]*\n")
            if not match:
                raise ValueError(f"Invalid block scalar {text}")
            style = match.group(1)
            text = text.removeprefix(match.group(0))
            indentation = re.search(r"^[ \t]*", text).group(0)
            lines = [line.removeprefix(indentation) for line in text.splitlines()]
            match style:
                case "|":
                    return "\n".join(lines) + "\n"
                case ">":
                    return " ".join(lines) + "\n"
                case "|-":
                    return "\n".join(lines)
                case ">-":
                    return " ".join(lines)
                case _:
                    raise ValueError(f"Invalid block scalar style {style}")
        case unknown_type:
            raise ValueError(f"Unsupported node type {unknown_type}")


def unescape_single_quoted(text: str) -> str:
    return re.sub(r"''", "'", text)


def unescape_double_quoted(text: str) -> str:
    return re.sub(
        r"\\(x[0-9a-zA-Z]{2}|u[0-9a-zA-Z]{4}|U[0-9a-zA-Z]{4}|.)",
        unescape_double_quoted_escape_sequence_match,
        text,
    )


def unescape_double_quoted_escape_sequence_match(match: re.Match[str]) -> str:
    match match.group(1)[0]:
        case "n":
            return "\n"
        case "r":
            return "\r"
        case "t":
            return "\t"
        case "b":
            return "\b"
        case "f":
            return "\f"
        case "v":
            return "\v"
        case "0":
            return "\0"
        case "x":
            return chr(int(match.group(1)[1:], 16))
        case "u":
            return chr(int(match.group(1)[1:], 16))
        case "U":
            return chr(int(match.group(1)[1:], 16))
        case _:
            return match.group(1)