import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import git

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "venv", ".venv", "env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "vendor", "third_party", ".next", "out", "coverage", ".tox",
    "target",  # Java/Rust build output
}

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
}

MAX_FILE_BYTES = 500_000  # skip files larger than 500 KB


@dataclass
class SourceFile:
    file_path: str   # relative to repo root
    language: str
    source_code: str


def load_repo(repo_url: str, clone_dir: str | None = None) -> tuple[str, list[SourceFile]]:
    """Clone repo_url and return (repo_root_path, list of SourceFile).

    If clone_dir is provided, clone there; otherwise use a temp directory
    that the caller is responsible for cleaning up.
    """
    target = clone_dir or tempfile.mkdtemp(prefix="reposage_")
    print(f"Cloning {repo_url} → {target}")
    git.Repo.clone_from(repo_url, target, depth=1)
    files = walk_repo(target)
    return target, files


def walk_repo(repo_root: str) -> list[SourceFile]:
    """Walk a local repo directory and return supported source files."""
    root = Path(repo_root)
    results: list[SourceFile] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path, root):
            continue
        lang = LANGUAGE_MAP.get(path.suffix.lower())
        if lang is None:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = str(path.relative_to(root))
        results.append(SourceFile(file_path=rel_path, language=lang, source_code=source))

    return results


def _should_skip(path: Path, root: Path) -> bool:
    """Return True if any path component is a directory that should be skipped."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in relative.parts)


def cleanup(repo_root: str) -> None:
    shutil.rmtree(repo_root, ignore_errors=True)
