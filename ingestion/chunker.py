from dataclasses import dataclass, field

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tsts
import tree_sitter_java as tsjava
import tree_sitter_go as tsgo
from tree_sitter import Language, Parser, Node

from ingestion.repo_loader import SourceFile

PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tsts.language_typescript())
TSX_LANGUAGE = Language(tsts.language_tsx())
JAVA_LANGUAGE = Language(tsjava.language())
GO_LANGUAGE = Language(tsgo.language())

_PARSERS: dict[str, Parser] = {}

# tree-sitter-typescript has its own node names for some constructs
_TS_CHUNK_TYPES = {
    "function_declaration", "arrow_function", "method_definition",
    "function_expression", "abstract_method_signature",
    "interface_declaration", "type_alias_declaration", "enum_declaration",
}


def _get_parser(language: str) -> Parser | None:
    if language not in _PARSERS:
        lang_obj = {
            "python": PY_LANGUAGE,
            "javascript": JS_LANGUAGE,
            "typescript": TS_LANGUAGE,
            "typescript_tsx": TSX_LANGUAGE,
            "java": JAVA_LANGUAGE,
            "go": GO_LANGUAGE,
        }.get(language)
        if lang_obj is None:
            return None
        parser = Parser(lang_obj)
        _PARSERS[language] = parser
    return _PARSERS[language]


# Node types that represent a top-level or method-level callable unit
_CHUNK_NODE_TYPES: dict[str, set[str]] = {
    # async def is function_definition in tree-sitter-python (async keyword is a child token)
    "python": {"function_definition"},
    "javascript": {"function_declaration", "arrow_function", "method_definition", "function_expression"},
    "typescript": _TS_CHUNK_TYPES,
    "typescript_tsx": _TS_CHUNK_TYPES,
    "java": {"method_declaration", "constructor_declaration"},
    "go": {"function_declaration", "method_declaration"},
}

MAX_CHUNK_LINES = 150
OVERLAP_LINES = 20


@dataclass
class CodeChunk:
    text: str
    file_path: str
    start_line: int   # 1-indexed
    end_line: int     # 1-indexed, inclusive
    language: str
    parent_class: str = ""


def chunk_file(source_file: SourceFile) -> list[CodeChunk]:
    """Return a list of CodeChunk for a single source file using AST chunking.
    Falls back to line-based chunking if the parser fails or the language
    is unsupported.
    """
    parser = _get_parser(source_file.language)
    if parser is None:
        return _line_based_chunks(source_file)

    source_bytes = source_file.source_code.encode("utf-8")
    tree = parser.parse(source_bytes)

    if tree.root_node.has_error and _error_ratio(tree.root_node) > 0.5:
        return _line_based_chunks(source_file)

    chunk_types = _CHUNK_NODE_TYPES.get(source_file.language, set())
    chunks: list[CodeChunk] = []
    lines = source_file.source_code.splitlines()

    _walk_tree(
        node=tree.root_node,
        source_bytes=source_bytes,
        lines=lines,
        file_path=source_file.file_path,
        language=source_file.language,
        chunk_types=chunk_types,
        chunks=chunks,
        parent_class="",
    )

    # If AST found nothing (e.g. a file with only top-level statements), fall back
    if not chunks:
        return _line_based_chunks(source_file)

    return chunks


def _walk_tree(
    node: Node,
    source_bytes: bytes,
    lines: list[str],
    file_path: str,
    language: str,
    chunk_types: set[str],
    chunks: list[CodeChunk],
    parent_class: str,
) -> None:
    current_class = parent_class

    # Detect class context for child nodes
    if node.type in ("class_definition", "class_declaration", "interface_declaration"):
        name_node = node.child_by_field_name("name")
        if name_node:
            current_class = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")

    if node.type in chunk_types:
        start_line = node.start_point[0] + 1  # tree-sitter is 0-indexed
        end_line = node.end_point[0] + 1
        text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")

        if end_line - start_line > MAX_CHUNK_LINES:
            chunks.extend(_split_large_chunk(text, file_path, start_line, language, current_class))
        else:
            chunks.append(CodeChunk(
                text=text,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                language=language,
                parent_class=current_class,
            ))
        # Don't recurse into a chunk — avoids double-counting nested functions
        return

    for child in node.children:
        _walk_tree(child, source_bytes, lines, file_path, language, chunk_types, chunks, current_class)


def _split_large_chunk(
    text: str, file_path: str, start_line: int, language: str, parent_class: str
) -> list[CodeChunk]:
    """Split an oversized function into overlapping sub-chunks."""
    lines = text.splitlines()
    chunks: list[CodeChunk] = []
    i = 0
    while i < len(lines):
        end = min(i + MAX_CHUNK_LINES, len(lines))
        chunk_text = "\n".join(lines[i:end])
        chunks.append(CodeChunk(
            text=chunk_text,
            file_path=file_path,
            start_line=start_line + i,
            end_line=start_line + end - 1,
            language=language,
            parent_class=parent_class,
        ))
        if end == len(lines):
            break
        i += MAX_CHUNK_LINES - OVERLAP_LINES
    return chunks


def _line_based_chunks(source_file: SourceFile) -> list[CodeChunk]:
    """Fallback: split source into overlapping line-based chunks."""
    lines = source_file.source_code.splitlines()
    chunks: list[CodeChunk] = []
    i = 0
    while i < len(lines):
        end = min(i + MAX_CHUNK_LINES, len(lines))
        chunk_text = "\n".join(lines[i:end])
        chunks.append(CodeChunk(
            text=chunk_text,
            file_path=source_file.file_path,
            start_line=i + 1,
            end_line=end,
            language=source_file.language,
            parent_class="",
        ))
        if end == len(lines):
            break
        i += MAX_CHUNK_LINES - OVERLAP_LINES
    return chunks


def _error_ratio(node: Node) -> float:
    """Approximate ratio of ERROR nodes to total nodes (iterative to avoid stack overflow)."""
    errors = 0
    total = 0
    stack = [node]
    while stack:
        current = stack.pop()
        total += 1
        if current.type == "ERROR":
            errors += 1
        stack.extend(current.children)
    return errors / max(total, 1)


def chunk_files(source_files: list[SourceFile]) -> list[CodeChunk]:
    """Chunk a list of SourceFile objects."""
    all_chunks: list[CodeChunk] = []
    for sf in source_files:
        all_chunks.extend(chunk_file(sf))
    return all_chunks
