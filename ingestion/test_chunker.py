from ingestion.chunker import chunk_file, CodeChunk
from ingestion.repo_loader import SourceFile

SAMPLE_PYTHON = """\
class MyClass:
    def method_one(self):
        return 1

    def method_two(self, x):
        return x * 2

def top_level_func(a, b):
    return a + b

def another_func():
    pass
"""

SAMPLE_PYTHON_NESTED = """\
class Outer:
    class Inner:
        def inner_method(self):
            pass

    def outer_method(self):
        return 42
"""

SAMPLE_GO = """\
package main

import "fmt"

func Hello() {
    fmt.Println("hello")
}

func Add(a, b int) int {
    return a + b
}
"""


def _make_sf(code: str, lang: str = "python", path: str = "test.py") -> SourceFile:
    return SourceFile(file_path=path, language=lang, source_code=code)


def test_each_function_is_own_chunk():
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    names = [c.text.split("(")[0].split()[-1] for c in chunks]
    assert "method_one" in names
    assert "method_two" in names
    assert "top_level_func" in names
    assert "another_func" in names


def test_no_duplicate_lines():
    """No two chunks from the same file should cover the exact same line range."""
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    ranges = [(c.start_line, c.end_line) for c in chunks]
    assert len(ranges) == len(set(ranges))


def test_line_numbers_are_correct():
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    top_level = next(c for c in chunks if "top_level_func" in c.text)
    # top_level_func starts at line 8 in SAMPLE_PYTHON (blank line 7 is between classes and functions)
    assert top_level.start_line == 8
    assert top_level.end_line == 9


def test_parent_class_captured():
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    method_chunks = [c for c in chunks if "method_one" in c.text or "method_two" in c.text]
    assert all(c.parent_class == "MyClass" for c in method_chunks)


def test_top_level_func_no_parent_class():
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    top_level = next(c for c in chunks if "top_level_func" in c.text)
    assert top_level.parent_class == ""


def test_go_chunking():
    chunks = chunk_file(_make_sf(SAMPLE_GO, lang="go", path="main.go"))
    assert len(chunks) >= 2
    func_names = [c.text.split("(")[0].split()[-1] for c in chunks]
    assert "Hello" in func_names
    assert "Add" in func_names


def test_large_function_is_split():
    big_func = "def big():\n" + "\n".join(f"    x_{i} = {i}" for i in range(300))
    chunks = chunk_file(_make_sf(big_func))
    assert len(chunks) > 1
    # Ensure overlap: last line of chunk n >= first line of chunk n+1 - OVERLAP
    for i in range(len(chunks) - 1):
        assert chunks[i].end_line >= chunks[i + 1].start_line - 1


def test_fallback_for_unparseable_language():
    """A file with language 'ruby' (unsupported) should still produce chunks."""
    sf = SourceFile(file_path="app.rb", language="ruby", source_code="def foo\n  1\nend\n")
    chunks = chunk_file(sf)
    assert len(chunks) >= 1


def test_metadata_fields_present():
    chunks = chunk_file(_make_sf(SAMPLE_PYTHON))
    for c in chunks:
        assert c.file_path == "test.py"
        assert c.language == "python"
        assert c.start_line >= 1
        assert c.end_line >= c.start_line
        assert isinstance(c.text, str) and len(c.text) > 0
