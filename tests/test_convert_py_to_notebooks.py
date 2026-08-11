import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONVERTER = REPOSITORY_ROOT / "scripts" / "convert_py_to_notebooks.py"


class ConvertPyToNotebooksTests(unittest.TestCase):
    def test_cli_mirrors_path_and_preserves_source(self):
        """Catches missing output, flattened paths, or altered source text."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory)
            source_path = source_root / "pkg" / "example.py"
            source_path.parent.mkdir()
            source_text = "# A Unicode comment: 你好\nprint('hello')\n"
            source_path.write_text(source_text, encoding="utf-8")
            output_root = source_root / "notebooks"

            result = subprocess.run(
                [sys.executable, str(CONVERTER), str(source_root), str(output_root)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            notebook_path = output_root / "pkg" / "example.ipynb"
            self.assertTrue(notebook_path.is_file())
            notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
            self.assertEqual(notebook["nbformat"], 4)
            self.assertEqual(notebook["cells"][0]["cell_type"], "code")
            self.assertEqual("".join(notebook["cells"][0]["source"]), source_text)
            self.assertEqual(source_path.read_text(encoding="utf-8"), source_text)

    def test_cli_excludes_generated_vcs_cache_and_environment_trees(self):
        """Catches accidental conversion of generated or dependency Python files."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory)
            output_root = source_root / "notebooks"
            included = source_root / "main.py"
            included.write_text("value = 1\n", encoding="utf-8")
            excluded_paths = [
                source_root / ".git" / "hook.py",
                source_root / ".venv" / "dependency.py",
                source_root / "venv" / "dependency.py",
                source_root / "__pycache__" / "cached.py",
                output_root / "generated.py",
            ]
            for excluded in excluded_paths:
                excluded.parent.mkdir(parents=True, exist_ok=True)
                excluded.write_text("value = 2\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(CONVERTER), str(source_root), str(output_root)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Converted 1 Python files", result.stdout)
            self.assertEqual(
                [path.relative_to(output_root) for path in output_root.rglob("*.ipynb")],
                [Path("main.ipynb")],
            )

    def test_check_accepts_matching_notebooks_and_rejects_source_drift(self):
        """Catches a validator that misses absent, malformed, or stale notebook content."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_root = Path(temporary_directory)
            output_root = source_root / "notebooks"
            source_path = source_root / "main.py"
            source_path.write_text("value = 1\n", encoding="utf-8")
            conversion = subprocess.run(
                [sys.executable, str(CONVERTER), str(source_root), str(output_root)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(conversion.returncode, 0, conversion.stderr)

            valid_check = subprocess.run(
                [
                    sys.executable,
                    str(CONVERTER),
                    str(source_root),
                    str(output_root),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(valid_check.returncode, 0, valid_check.stderr)
            self.assertIn("Validated 1 notebooks", valid_check.stdout)

            source_path.write_text("value = 2\n", encoding="utf-8")
            stale_check = subprocess.run(
                [
                    sys.executable,
                    str(CONVERTER),
                    str(source_root),
                    str(output_root),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(stale_check.returncode, 0)
            self.assertIn("source mismatch", stale_check.stderr)


if __name__ == "__main__":
    unittest.main()
