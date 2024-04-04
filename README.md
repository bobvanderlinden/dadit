# dadit

A CLI tool to manipulate structured files, like YAML.

The goal is to keep the structure, formatting and comments intact and only make changes to those parts of the file that needs changing.

## Usage

Consider the following file `data.yaml`:

```yaml
a: hello
b: | # This is an explanation.
  These
  are
  multiple
  lines
```

The file can be transformed using:

```console
$ dadit patch --format yaml --replace /b '"world"' data.yaml
a: hello
b: world # This is an explanation.
```
