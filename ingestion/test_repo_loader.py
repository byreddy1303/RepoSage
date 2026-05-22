import os
import tempfile
from pathlib import Path

from ingestion.repo_loader import SourceFile, walk_repo


def _make_repo(files: dict[str, str]) -> str:
    """Create a temp directory with the given file structure."""
    root = tempfile.mkdtemp(prefix="reposage_test_")
    for rel_path, content in files.items():
        full = Path(root) / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return root


def test_walk_finds_python_files():
    root = _make_repo({
        "main.py": "def main(): pass",
        "utils/helper.py": "def help(): pass",
    })
    try:
        files = walk_repo(root)
        paths = {f.file_path for f in files}
        assert "main.py" in paths
        assert "utils/helper.py" in paths
        assert all(f.language == "python" for f in files)
    finally:
        import shutil; shutil.rmtree(root)


def test_walk_skips_junk_dirs():
    root = _make_repo({
        "src/app.py": "x = 1",
        "node_modules/lib.js": "module.exports = {}",
        "__pycache__/app.cpython-312.pyc": "junk",
        "venv/lib/python3.12/site.py": "import sys",
        ".git/config": "[core]",
    })
    try:
        files = walk_repo(root)
        paths = {f.file_path for f in files}
        assert "src/app.py" in paths
        assert not any("node_modules" in p for p in paths)
        assert not any("__pycache__" in p for p in paths)
        assert not any("venv" in p for p in paths)
        assert not any(".git" in p for p in paths)
    finally:
        import shutil; shutil.rmtree(root)


def test_walk_multi_language():
    root = _make_repo({
        "app.py": "pass",
        "index.js": "console.log(1)",
        "Main.java": "class Main {}",
        "main.go": "package main",
        "style.css": "body {}",      # not supported — should be skipped
        "README.md": "# readme",     # not supported
    })
    try:
        files = walk_repo(root)
        langs = {f.language for f in files}
        assert "python" in langs
        assert "javascript" in langs
        assert "java" in langs
        assert "go" in langs
        paths = {f.file_path for f in files}
        assert "style.css" not in paths
        assert "README.md" not in paths
    finally:
        import shutil; shutil.rmtree(root)


def test_walk_skips_large_files():
    root = _make_repo({
        "small.py": "x = 1",
        "big.py": "x = 1\n" * 300_000,  # ~1.8 MB
    })
    try:
        files = walk_repo(root)
        paths = {f.file_path for f in files}
        assert "small.py" in paths
        assert "big.py" not in paths
    finally:
        import shutil; shutil.rmtree(root)
