from tree_sitter import Node, Tree, Parser
from typing import Iterable, Any, Callable

type Selector = Callable[[Node], Iterable[Node]]

def query(node, *selectors: Selector) -> Iterable[Node]:
    return chain(*selectors)(node)


def chain(*selectors: Selector) -> Selector:
    def chain_selector(node: Node) -> Iterable[Node]:
        nodes = [node]
        for selector in selectors:
            nodes = [node_out for node_in in nodes for node_out in selector(node_in)]
        return nodes

    return chain_selector


def children(node: Node) -> Iterable[Node]:
    for child in node.children:
        yield child


def conditional(predicate: Callable[[Node], bool]) -> Selector:
    def conditional_selector(node: Node):
        if predicate(node):
            yield node

    return conditional_selector


def filter(selector: Selector) -> Selector:
    def filter_selector(node: Node):
        if any(True for _ in selector(node)):
            yield node

    return filter_selector


def parent(node: Node) -> Iterable[Node]:
    if node.parent:
        yield node.parent


def text(str) -> Selector:
    return conditional(lambda node: node.text == str)


def type(str) -> Selector:
    return conditional(lambda node: node.type == str)


def field(str) -> Selector:
    def field_selector(node: Node):
        return node.children_by_field_name(str)

    return field_selector


def single(nodes: Iterable[Node]) -> Node:
    match [*nodes]:
        case [node]:
            return node
        case []:
            raise ValueError("Expected a single node, got none")
        case _:
            raise ValueError("Expected a single node, got more than one")


def union(*selectors: Selector) -> Selector:
    def union_selector(node: Node):
        return {child for selector in selectors for child in selector(node)}

    return union_selector
