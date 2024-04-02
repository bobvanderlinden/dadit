from typing import List
from dataclasses import dataclass
from abc import ABC
from .json import JSON


@dataclass
class JSONPointer:
    parts: list[str]

    @classmethod
    def parse(cls, str: str):
        if not str.startswith("/"):
            raise ValueError(f"Invalid JSON pointer {str}")
        return cls(
            parts=[
                part.replace("~1", "/").replace("~0", "~")
                for part in str.split("/")[1:]
            ]
        )

    def __str__(self):
        return "/" + "/".join(
            [part.replace("~", "~0").replace("/", "~1") for part in self.parts]
        )

    def __eq__(self, other):
        return self.parts == other.parts


@dataclass
class JSONPatchOperation(ABC):
    @classmethod
    def from_json(cls, value: JSON):
        match value:
            case {"op": "add", "path": str(path), "value": value}:
                return JSONPatchAdd(
                    path=JSONPointer.parse(path),
                    value=value,
                )
            case {"op": "remove", "path": str(path)}:
                return JSONPatchRemove(
                    path=JSONPointer.parse(path),
                )
            case {"op": "replace", "path": str(path), "value": value}:
                return JSONPatchReplace(
                    path=JSONPointer.parse(path),
                    value=value,
                )
            case {"op": "move", "from": str(from_), "path": str(path)}:
                return JSONPatchMove(
                    from_=JSONPointer.parse(from_),
                    path=JSONPointer.parse(path),
                )
            case {"op": "copy", "from": str(from_), "path": str(path)}:
                return JSONPatchCopy(
                    from_=JSONPointer.parse(from_),
                    path=JSONPointer.parse(path),
                )
            case {"op": "test", "path": str(path), "value": value}:
                return JSONPatchTest(
                    path=JSONPointer.parse(path),
                    value=value,
                )
            case _:
                raise ValueError(f"Unsupported JSON patch operation {value}")


@dataclass
class JSONPatchAdd(JSONPatchOperation):
    op = "add"
    path: JSONPointer
    value: JSON


@dataclass
class JSONPatchRemove(JSONPatchOperation):
    op = "remove"
    path: JSONPointer


@dataclass
class JSONPatchReplace(JSONPatchOperation):
    op = "replace"
    path: JSONPointer
    value: JSON


@dataclass
class JSONPatchMove(JSONPatchOperation):
    op = "move"
    from_: JSONPointer
    path: JSONPointer


@dataclass
class JSONPatchCopy(JSONPatchOperation):
    op = "copy"
    from_: JSONPointer
    path: JSONPointer


@dataclass
class JSONPatchTest(JSONPatchOperation):
    op = "test"
    path: JSONPointer
    value: JSON

type JSONPatch = List[JSONPatchOperation]
