"""Shared fixtures: locating build.py, and a fake `graphify` on PATH.

build.py is an orchestrator — its whole observable contract is which graphify
commands it runs, with which flags, in which order, plus what it leaves on disk.
So the seam is its own CLI, and the fake shim is how we watch the subprocess
boundary without paying for real extraction on every assertion.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_PY = REPO_ROOT / ".claude" / "skills" / "Graphify" / "scripts" / "build.py"
TINY_CORPUS = Path(__file__).resolve().parent / "fixtures" / "tiny-corpus"

SHIM = r'''#!{python}
"""Fake `graphify`: records argv, then fakes just enough output to be believable."""
import json, os, sys
from pathlib import Path

argv = sys.argv[1:]
with open(os.environ["GRAPHIFY_SHIM_LOG"], "a") as fh:
    fh.write("\t".join(argv) + "\n")

if argv and argv[0] == os.environ.get("GRAPHIFY_SHIM_FAIL"):
    print("[graphify] simulated failure", file=sys.stderr)
    sys.exit(1)

if not argv:
    sys.exit(2)
cmd, target = argv[0], Path(argv[1]) if len(argv) > 1 else Path(".")
out = target / "graphify-out"

if cmd == "extract" and not os.environ.get("GRAPHIFY_SHIM_NO_GRAPH"):
    out.mkdir(parents=True, exist_ok=True)
    (out / "graph.json").write_text(json.dumps({"nodes": [{"id": "a"}], "links": []}))
    print(f"[graphify extract] wrote {out / 'graph.json'}: 1 nodes, 0 edges, 2 communities")
elif cmd == "label":
    out.mkdir(parents=True, exist_ok=True)
    # Real graphify never leaves "Community N" after an LLM failure -- it falls back to
    # hub-derived names. The sentinel survives only when clustering ran without labelling,
    # which is the state this mode reproduces.
    if os.environ.get("GRAPHIFY_SHIM_PLACEHOLDER"):
        labels = {"0": "Community 0", "1": "Named Thing"}
    else:
        labels = {"0": "Greeting Module", "1": "Text Utilities"}
    if not os.environ.get("GRAPHIFY_SHIM_NO_LABELS"):
        (out / ".graphify_labels.json").write_text(json.dumps(labels))
    print("Done - 2 communities. GRAPH_REPORT.md, graph.json and graph.html updated.")
'''


@pytest.fixture
def corpus(tmp_path):
    """A git repo holding the tiny fixture corpus."""
    root = tmp_path / "corpus"
    root.mkdir()
    for src in TINY_CORPUS.iterdir():
        shutil.copy(src, root / src.name)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


@pytest.fixture
def run_build(tmp_path, monkeypatch):
    """Run build.py with a fake graphify on PATH; return (result, recorded argv lines)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shim = bindir / "graphify"
    shim.write_text(SHIM.replace("{python}", sys.executable, 1))
    shim.chmod(0o755)
    log = tmp_path / "graphify-calls.log"

    def _run(*args, **shim_env):
        env = dict(os.environ)
        # PATH_STRIP_GIT leaves only the shim on PATH, so `git` genuinely cannot be found.
        env["PATH"] = str(bindir) if shim_env.pop("PATH_STRIP_GIT", None) else \
            f"{bindir}{os.pathsep}{env['PATH']}"
        env["GRAPHIFY_SHIM_LOG"] = str(log)
        env.update({k: str(v) for k, v in shim_env.items() if v})
        result = subprocess.run(
            [sys.executable, str(BUILD_PY), *map(str, args)],
            capture_output=True, text=True, env=env,
        )
        calls = [line.split("\t") for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return _run
