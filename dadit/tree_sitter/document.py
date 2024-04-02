from tree_sitter_languages import get_parser as _get_parser
from tree_sitter import Tree, Parser
from dataclasses import dataclass
from functools import lru_cache


@lru_cache(maxsize=None)
def get_parser(language: str):
    return _get_parser(language=language)


@dataclass
class Document:
    text: bytes
    tree: Tree
    parser: Parser

    @classmethod
    def parse_raw(cls, text: bytes, parser: Parser):
        return cls(
            text=text,
            tree=parser.parse(text),
            parser=parser,
        )

    @classmethod
    def parse(cls, text: str, language: str):
        parser = get_parser(language)
        return cls.parse_raw(text.encode("utf-8"), parser)
