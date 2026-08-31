#!/usr/bin/env python3
"""Build or refresh a graphify knowledge graph for a corpus."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def graphify(*args):
    if subprocess.run(["graphify", *args]).returncode != 0:
        sys.exit(f"build.py: `graphify {args[0]}` failed -- see its output above.")


def exclude_from_git(root):
    """graphify-out/ runs to megabytes and .gitignore is tracked; git itself resolves worktrees, submodules and relative gitdir pointers, so don't re-derive them."""
    try:
        seen = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return  # no git, or not a repo -- the local exclude is best-effort
    path = root / seen / "info" / "exclude"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""
    if "graphify-out/" not in text.splitlines():
        path.write_text(f"{text.rstrip()}\ngraphify-out/\n".lstrip())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", type=Path,
                    help="corpus root to index; graphify-out/ is written inside it")
    ap.add_argument("--semantic", action="store_true",
                    help="also index docs, papers and images through the claude-cli LLM "
                         "backend (minutes). Omitted: code only, local AST, no LLM, seconds")
    ap.add_argument("--force", action="store_true",
                    help="re-scan everything instead of diffing against the existing graph")
    a = ap.parse_args()
    if not a.path.is_dir():
        sys.exit(f"build.py: {a.path} is not a directory")
    graph = a.path / "graphify-out" / "graph.json"
    exclude_from_git(a.path)

    was = graph.stat().st_mtime_ns if graph.exists() else 0
    graphify("extract", str(a.path),
             *(["--backend", "claude-cli"] if a.semantic else ["--code-only"]),
             *(["--force"] if a.force else []))
    if not graph.exists() or graph.stat().st_mtime_ns == was:
        sys.exit(f"build.py: extract left {graph} unwritten; refusing to label a stale graph.")
    graphify("label", str(a.path), "--backend", "claude-cli")
    sidecar = graph.parent / ".graphify_labels.json"
    names = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    unnamed = [k for k, v in names.items() if v.removeprefix("Community ").isdigit()]
    if unnamed or not names:
        sys.exit(f"build.py: {len(unnamed) or 'all'} of {len(names)} communities are unnamed; "
                 f"they are part of what `query` matches. Re-run `graphify label {a.path} --backend claude-cli`.")
    print(f"\nbuild.py: {len(names)} communities named -> {graph.parent}")

main()
