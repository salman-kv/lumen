"""Fills code snippets into a markdown template straight from the source files, so a document can never show code that
differs from the real code.

  cd backend && uv run python ../scripts/expand_code.py ../docs/IMPLEMENTATION_GUIDE.src.md ../docs/IMPLEMENTATION_GUIDE.md

Directives (each on its own line in the template):
  @@py <path> <name> [<name> ...]        top-level functions or classes of a Python file; name:a-b keeps lines a..b of it
  @@js <path> <name>                     a JavaScript/JSX function or const arrow function, found by brace matching
  @@between <path> ||| <start> ||| <end> from the line matching <start> up to (not including) the line matching <end>
  @@file <path>                          the whole file
  @@filetable                            a table of the main source files with their line counts
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANG = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".bat": "bat", ".yml": "yaml", ".md": "markdown",
        ".json": "json", ".example": "text"}


def lines_of(path: str) -> list[str]:
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


def fence(code: str, path: str) -> str:
    lang = "dockerfile" if Path(path).name == "Dockerfile" else LANG.get(Path(path).suffix, "text")
    return f"```{lang}\n{code.rstrip()}\n```"


def py(path: str, names: list[str]) -> str:
    src = "\n".join(lines_of(path))
    tree, lines, parts = ast.parse(src), src.splitlines(), []
    for spec in names:
        name, _, rng = spec.partition(":")
        node = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                     and n.name == name), None)
        if node is None:
            raise SystemExit(f"{path}: no top-level function or class named {name!r}")
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        seg = lines[start - 1: node.end_lineno]
        if rng:
            a, b = (int(x) for x in rng.split("-"))
            seg = seg[a - 1: b] + (["    # ... (the function continues)"] if b < len(seg) else [])
        parts.append("\n".join(seg))
    return fence("\n\n\n".join(parts), path)


def js(path: str, name: str) -> str:
    lines = lines_of(path)
    rx = re.compile(rf"^\s*(export\s+)?(default\s+)?(async\s+)?(function\s+{re.escape(name)}\b|const\s+{re.escape(name)}\s*=)")
    start = next((i for i, ln in enumerate(lines) if rx.match(ln)), None)
    if start is None:
        raise SystemExit(f"{path}: no JavaScript function named {name!r}")
    depth, opened, end = 0, False, start
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == "{":
                depth, opened = depth + 1, True
            elif ch == "}":
                depth -= 1
        if opened and depth <= 0:
            end = i
            break
    seg = lines[start: end + 1]
    indent = len(seg[0]) - len(seg[0].lstrip())
    return fence("\n".join(ln[indent:] for ln in seg), path)


def between(path: str, start: str, end: str | None) -> str:
    lines = lines_of(path)
    a = next((i for i, ln in enumerate(lines) if re.search(start, ln)), None)
    if a is None:
        raise SystemExit(f"{path}: no line matching {start!r}")
    b = next((i for i in range(a + 1, len(lines)) if end and re.search(end, lines[i])), len(lines))
    return fence("\n".join(lines[a:b]), path)


def filetable() -> str:
    groups = [("Backend (`backend/app`)", sorted((ROOT / "backend/app").glob("*.py"))),
              ("Backend tests (`backend/tests`)", sorted((ROOT / "backend/tests").glob("*.py"))),
              ("Frontend (`frontend/src`)", sorted((ROOT / "frontend/src").rglob("*.jsx")) + sorted((ROOT / "frontend/src").glob("*.js"))),
              ("Scripts (`scripts`)", sorted((ROOT / "scripts").glob("*")))]
    rows = ["| File | Lines |", "|---|---|"]
    total = 0
    for title, files in groups:
        rows.append(f"| **{title}** | |")
        for f in files:
            if f.is_file() and f.name != "__init__.py":
                n = len(f.read_text(encoding="utf-8").splitlines())
                total += n
                rows.append(f"| `{f.relative_to(ROOT).as_posix()}` | {n} |")
    rows.append(f"| **Total** | **{total}** |")
    return "\n".join(rows)


def expand(line: str) -> str | None:
    if not line.startswith("@@"):
        return None
    cmd, _, rest = line[2:].strip().partition(" ")
    if cmd == "py":
        path, *names = rest.split()
        return py(path, names)
    if cmd == "js":
        path, name = rest.split()
        return js(path, name)
    if cmd == "between":
        path, start, *end = (x.strip() for x in rest.split("|||"))
        return between(path, start, end[0] if end else None)
    if cmd == "file":
        return fence("\n".join(lines_of(rest.strip())), rest.strip())
    if cmd == "filetable":
        return filetable()
    raise SystemExit(f"unknown directive: {line}")


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    result = []
    for line in src.read_text(encoding="utf-8").splitlines():
        result.append(expand(line) or line)
    out.write_text("\n".join(result) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(result)} lines)")


if __name__ == "__main__":
    main()
