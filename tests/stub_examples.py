import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

import pytest

STUBFILE = Path(__file__).resolve().parents[1] / "python/chronosapien/__init__.pyi"
PYBLOCK = re.compile(
    r"^[ \t]*```python[ \t]*\n(.*?)^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL
)


@dataclass(frozen=True)
class Example:
    scope: str
    line: int
    code: str


def find_examples(node: ast.AST, source: str, scope: str) -> Iterator[Example]:
    if isinstance(node, ast.AsyncFunctionDef):
        return

    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        scope = f"{scope}.{node.name}"

    if (
        isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
        and ast.get_docstring(node) is not None
    ):
        docstring_node = node.body[0]
        docstring = ast.get_source_segment(source, docstring_node)
        if docstring is not None:
            for block in PYBLOCK.finditer(docstring):
                line = docstring_node.lineno + docstring.count("\n", 0, block.start(1))
                yield Example(scope, line, block[1])

    for child in ast.iter_child_nodes(node):
        yield from find_examples(child, source, scope)


class StubExample(pytest.Item):
    def __init__(
        self, *, name: str, parent: pytest.Collector, example: Example
    ) -> None:
        super().__init__(name=name, parent=parent)  # pyrefly: ignore[partially-unknown-type]
        self.example = example

    def runtest(self) -> None:
        raw = self.example.code
        source = dedent(raw)
        indent = next(
            (
                len(original) - len(line)
                for original, line in zip(
                    raw.split("\n"), source.split("\n"), strict=True
                )
                if line != ""
            ),
            0,
        )

        # Preserve the original line and column positions in tracebacks.
        path = str(self.path)
        tree = ast.parse("\n" * (self.example.line - 1) + source, filename=path)
        for node in ast.walk(tree):
            for attribute in ("col_offset", "end_col_offset"):
                offset = getattr(node, attribute, None)
                if isinstance(offset, int):
                    setattr(node, attribute, offset + indent)
        code = compile(tree, path, "exec", optimize=0)
        exec(code, {})  # noqa: S102

    # typing.override was added in Python 3.12.
    def reportinfo(self) -> tuple[Path, int, str]:  # pyrefly: ignore[missing-override-decorator]
        return self.path, self.example.line - 1, self.name


class StubFile(pytest.File):
    def collect(self) -> Iterator[pytest.Item]:
        source = self.path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(self.path))
        examples = list(find_examples(tree, source, self.path.parent.name))
        if len(examples) == 0:
            raise self.CollectError(
                f"No Python docstring blocks found in {self.path.name}"
            )

        for example in examples:
            name = f"{example.scope}:{example.line}"
            yield StubExample.from_parent(  # pyrefly: ignore[partially-unknown-type]
                self, name=name, example=example
            )


def pytest_collect_file(
    file_path: Path, parent: pytest.Collector
) -> pytest.File | None:
    if file_path == STUBFILE:
        return StubFile.from_parent(  # pyrefly: ignore[partially-unknown-type]
            parent, path=file_path
        )
    return None
