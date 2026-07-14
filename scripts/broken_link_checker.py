#!/usr/bin/env python3
"""Check all Markdown files for broken internal links."""
import os
import re
import sys
from pathlib import Path

def find_md_files(root):
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith('.md'):
                yield os.path.join(dirpath, f)

def extract_links(filepath):
    links = []
    with open(filepath) as f:
        for i, line in enumerate(f, 1):
            for m in re.finditer(r'\[([^\]]*)\]\(([^)]+)\)', line):
                links.append((i, m.group(1), m.group(2)))
    return links

def main():
    repo = Path(__file__).resolve().parent.parent
    os.chdir(repo)

    all_files = set()
    for f in find_md_files('.'):
        all_files.add(os.path.relpath(f))

    broken = 0
    for fpath in sorted(all_files):
        for lineno, text, target in extract_links(fpath):
            if target.startswith(('http://', 'https://', '#')):
                continue
            # Remove anchor
            target_path = target.split('#')[0]
            if not target_path:
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(fpath), target_path))
            if not os.path.exists(resolved):
                print(f"BROKEN: {fpath}:{lineno}: [{text}]({target}) -> {resolved} (not found)")
                broken += 1

    if broken:
        print(f"\n{boken} broken link(s) found.")
        sys.exit(1)
    print("✓ All internal links valid.")
    sys.exit(0)

if __name__ == '__main__':
    main()
