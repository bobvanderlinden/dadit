from io import StringIO
from ruamel.yaml import YAML, Dumper
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


def loads(text: str) -> JSON:
    with StringIO(text) as stream:
        _yaml.load(stream)
        return stream.getvalue()
