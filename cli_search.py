#!/usr/bin/env python3
"""CLI: ask a question, see the top-k retrieved code chunks."""
import sys
from retrieval.search import search


def main() -> None:
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("Question: ").strip()
        if not query:
            print("No question provided.")
            sys.exit(1)

    print(f'\nSearching for: "{query}"\n{"─" * 60}')
    results = search(query, top_k=5)

    if not results:
        print("No results found.")
        return

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r.citation}  (score: {r.score:.4f})")
        if r.parent_class:
            print(f"    class: {r.parent_class}  |  language: {r.language}")
        else:
            print(f"    language: {r.language}")
        print("    " + "─" * 56)
        # Print first 20 lines of the chunk
        lines = r.text.splitlines()[:20]
        for line in lines:
            print("    " + line)
        if len(r.text.splitlines()) > 20:
            print(f"    ... ({len(r.text.splitlines()) - 20} more lines)")


if __name__ == "__main__":
    main()
