from typing import Iterable
from dataclasses import dataclass
from .document import Document


@dataclass
class Edit:
    start_byte: int


@dataclass
class Replace(Edit):
    end_byte: int
    content: bytes


@dataclass
class Insert(Edit):
    content: bytes


@dataclass
class Remove(Edit):
    end_byte: int


def apply_edits(document: Document, edits: Iterable[Edit]) -> Document:
    # Make sure edits are ordered from end to beginning of the file.
    # This is to make sure one edit won't change the offsets of other edits.
    edits = list(edits)
    edits.sort(key=lambda edit: edit.start_byte, reverse=True)

    for edit in edits:
        match edit:
            case Replace(start_byte, end_byte, content):
                document = Document(
                    text=document.text[:start_byte]
                    + content
                    + document.text[end_byte:],
                    tree=document.tree,
                    parser=document.parser,
                )
            case Insert(start_byte, content):
                document = Document(
                    text=document.text[:start_byte]
                    + content
                    + document.text[start_byte:],
                    tree=document.tree,
                    parser=document.parser,
                )
            case Remove(start_byte, end_byte):
                document = Document(
                    text=document.text[:start_byte] + document.text[end_byte:],
                    tree=document.tree,
                    parser=document.parser,
                )
            case _:
                raise ValueError(f"Unsupported edit type {edit}")
    return document
