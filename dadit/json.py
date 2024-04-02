from typing import Dict, List
from json import dumps as _dumps, loads as _loads

type JSON = "JSONScalar" | "JSONObject" | "JSONArray"
type JSONObject = Dict[str, JSON]
type JSONArray = List[JSON]
type JSONScalar = str | int | float | bool | None

def dumps(data: JSON) -> str:
    return _dumps(data)

def loads(json: str) -> JSON:
  return _loads(json)