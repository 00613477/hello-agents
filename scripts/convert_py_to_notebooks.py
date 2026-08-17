#!/usr/bin/env python3
"""Convert a tree of Python files to mirrored Jupyter notebooks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tokenize


EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".nox",
    ".tox",
    ".venv",
    ".worktrees",
    "ENV",
    "__pycache__",
    "env",
    "node_modules",
    "venv",
}


def is_below(path: Path, directory: Path) -> bool:
    """Return whether path is directory or one of its descendants."""
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def discover_python_files(source_root: Path, output_root: Path) -> list[Path]:
    """Return Python files below source_root in stable path order."""
    return sorted(
        path
        for path in source_root.rglob("*.py")
        if path.is_file()
        and not is_below(path, output_root)
        and not EXCLUDED_DIRECTORY_NAMES.intersection(path.relative_to(source_root).parts)
    )


def read_source(source_path: Path) -> str:
    """Read Python source using its declared PEP 263 encoding."""
    with tokenize.open(source_path) as source_file:
        return source_file.read()


def build_notebook(source_text: str) -> dict[str, object]:
    """Build a Jupyter Notebook v4 document containing one code cell."""
    return {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source_text.splitlines(keepends=True),
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def convert_tree(source_root: Path, output_root: Path) -> list[Path]:
    """Convert all Python files below source_root into output_root."""
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    outputs: list[Path] = []
    for source_path in discover_python_files(source_root, output_root):
        relative_path = source_path.relative_to(source_root).with_suffix(".ipynb")
        notebook_path = output_root / relative_path
        notebook_path.parent.mkdir(parents=True, exist_ok=True)
        notebook_path.write_text(
            json.dumps(build_notebook(read_source(source_path)), ensure_ascii=False, indent=1)
            + "\n",
            encoding="utf-8",
        )
        outputs.append(notebook_path)
    return outputs


def validate_tree(source_root: Path, output_root: Path) -> tuple[int, list[str]]:
    """Validate notebook presence, structure, and source fidelity."""
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    source_paths = discover_python_files(source_root, output_root)
    expected_notebooks = {
        output_root / path.relative_to(source_root).with_suffix(".ipynb")
        for path in source_paths
    }
    actual_notebooks = set(output_root.rglob("*.ipynb")) if output_root.exists() else set()
    errors = [
        f"unexpected notebook: {path}"
        for path in sorted(actual_notebooks - expected_notebooks)
    ]
    for source_path in source_paths:
        notebook_path = output_root / source_path.relative_to(source_root).with_suffix(
            ".ipynb"
        )
        if not notebook_path.is_file():
            errors.append(f"missing notebook: {notebook_path}")
            continue
        try:
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            errors.append(f"invalid notebook JSON: {notebook_path}: {error}")
            continue
        cells = notebook.get("cells")
        if notebook.get("nbformat") != 4 or not isinstance(cells, list) or len(cells) != 1:
            errors.append(f"invalid notebook structure: {notebook_path}")
            continue
        cell = cells[0]
        if cell.get("cell_type") != "code" or not isinstance(cell.get("source"), list):
            errors.append(f"invalid code cell: {notebook_path}")
            continue
        if "".join(cell["source"]) != read_source(source_path):
            errors.append(f"source mismatch: {source_path} -> {notebook_path}")
    return len(source_paths), errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate existing notebooks without rewriting them",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        source_count, errors = validate_tree(args.source_root, args.output_root)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"Validated {source_count} notebooks in {args.output_root}")
        return 0
    outputs = convert_tree(args.source_root, args.output_root)
    print(f"Converted {len(outputs)} Python files into {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
