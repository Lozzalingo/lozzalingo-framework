#!/usr/bin/env python3
"""
Lint HTML templates for <a> and <button> elements missing name= attributes.

Usage:
    python lint_unnamed.py                    # scan ./templates/
    python lint_unnamed.py /path/to/templates # scan specific dir

Exit code 0 = all good, 1 = unnamed elements found.
Output is designed to be piped into an AI prompt or CI check.
"""
import os
import re
import sys

# Directories to skip (admin/dashboard templates don't need tracking)
SKIP_DIRS = {'admin', 'dashboard', 'auth', 'email', '__pycache__'}

# Regex: match <a ...> or <button ...> tags (non-greedy, handles multi-line)
TAG_RE = re.compile(
    r'<(a|button)\b([^>]*)>',
    re.IGNORECASE | re.DOTALL
)

# Check if tag has name= or id= attribute
HAS_NAME_RE = re.compile(r'\bname\s*=', re.IGNORECASE)
HAS_ID_RE = re.compile(r'\bid\s*=', re.IGNORECASE)

# Skip patterns: Jinja comments, script blocks, purely anchor hrefs
SKIP_HREF_RE = re.compile(r'''href\s*=\s*["']#["']''', re.IGNORECASE)


SCRIPT_RE = re.compile(r'<script\b[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)


def scan_file(filepath):
    """Scan a single HTML file, return list of (line_no, tag, snippet) for unnamed elements."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Build set of positions inside <script> blocks to skip
    script_ranges = []
    for m in SCRIPT_RE.finditer(content):
        script_ranges.append((m.start(), m.end()))

    def in_script(pos):
        return any(s <= pos < e for s, e in script_ranges)

    issues = []
    for match in TAG_RE.finditer(content):
        # Skip tags inside <script> blocks
        if in_script(match.start()):
            continue
        tag = match.group(1).lower()
        attrs = match.group(2)

        # Skip if it already has name= or id=
        if HAS_NAME_RE.search(attrs) or HAS_ID_RE.search(attrs):
            continue

        # Skip pure anchor links (#)
        if tag == 'a' and SKIP_HREF_RE.search(attrs):
            continue

        # Skip disabled buttons (cosmetic, not interactive)
        if 'disabled' in attrs and tag == 'button':
            continue

        # Calculate line number
        line_no = content[:match.start()].count('\n') + 1

        # Build a readable snippet
        full_tag = match.group(0)
        snippet = full_tag[:120] + ('...' if len(full_tag) > 120 else '')

        issues.append((line_no, tag, snippet))

    return issues


def scan_directory(template_dir):
    """Scan all HTML files in a directory tree."""
    all_issues = {}

    for root, dirs, files in os.walk(template_dir):
        # Skip admin/dashboard directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for fname in sorted(files):
            if not fname.endswith('.html'):
                continue

            filepath = os.path.join(root, fname)
            issues = scan_file(filepath)
            if issues:
                rel_path = os.path.relpath(filepath, template_dir)
                all_issues[rel_path] = issues

    return all_issues


def main():
    # Determine template directory
    if len(sys.argv) > 1:
        template_dir = sys.argv[1]
    else:
        template_dir = os.path.join(os.getcwd(), 'templates')

    if not os.path.isdir(template_dir):
        print(f"Error: {template_dir} is not a directory", file=sys.stderr)
        sys.exit(2)

    all_issues = scan_directory(template_dir)

    if not all_issues:
        print("All <a> and <button> elements have name attributes.")
        sys.exit(0)

    # Output in a format useful for both humans and AI prompts
    total = sum(len(v) for v in all_issues.values())
    print(f"UNNAMED ELEMENTS DETECTED: {total} element(s) across {len(all_issues)} file(s)\n")
    print("Every <a> and <button> in public templates needs a name= attribute")
    print("for analytics tracking. Elements without names show as 'unnamed' in analytics.\n")

    for filepath, issues in sorted(all_issues.items()):
        print(f"--- {filepath} ---")
        for line_no, tag, snippet in issues:
            print(f"  Line {line_no}: <{tag}> {snippet}")
        print()

    print(f"FIX: Add name=\"descriptive_name\" to each element above.")
    print(f"     Use patterns like: name=\"ticker_video_1\", name=\"upvote_{{{{ project.slug }}}}\", etc.")
    sys.exit(1)


if __name__ == '__main__':
    main()
