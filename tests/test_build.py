"""build.py's contract, watched at its own CLI.

Two seams, deliberately: the fake-shim tests pin *which graphify commands get
issued* (fast enough to cover every branch), and one integration test runs the
real CLI so a flag that graphify renames breaks the suite instead of going
quiet.
"""

import json
import subprocess

import pytest

from conftest import BUILD_PY


def flags(calls, subcommand):
    """The single recorded invocation of `graphify <subcommand>`."""
    matching = [c for c in calls if c and c[0] == subcommand]
    assert len(matching) == 1, f"expected exactly one `graphify {subcommand}`, got {matching}"
    return matching[0]


# --- which commands get issued -------------------------------------------------

def test_default_run_indexes_code_only(run_build, corpus):
    result, calls = run_build(corpus)
    assert result.returncode == 0, result.stderr
    extract = flags(calls, "extract")
    assert "--code-only" in extract
    assert "--backend" not in extract


def test_semantic_run_names_the_backend_that_is_never_auto_selected(run_build, corpus):
    result, calls = run_build(corpus, "--semantic")
    assert result.returncode == 0, result.stderr
    extract = flags(calls, "extract")
    assert "--code-only" not in extract
    assert extract[extract.index("--backend") + 1] == "claude-cli"


def test_labelling_always_names_that_backend_too(run_build, corpus):
    _, calls = run_build(corpus)
    label = flags(calls, "label")
    assert label[label.index("--backend") + 1] == "claude-cli"


def test_force_reaches_extract(run_build, corpus):
    _, calls = run_build(corpus, "--force")
    assert "--force" in flags(calls, "extract")


def test_extract_runs_before_label(run_build, corpus):
    _, calls = run_build(corpus)
    order = [c[0] for c in calls]
    assert order.index("extract") < order.index("label")


# --- filesystem postconditions -------------------------------------------------

def test_graph_output_is_excluded_from_git_locally(run_build, corpus):
    run_build(corpus)
    exclude = (corpus / ".git" / "info" / "exclude").read_text()
    assert "graphify-out/" in exclude


def test_the_exclude_entry_is_not_appended_twice(run_build, corpus):
    run_build(corpus)
    run_build(corpus)
    exclude = (corpus / ".git" / "info" / "exclude").read_text()
    assert exclude.splitlines().count("graphify-out/") == 1


def test_existing_exclude_content_survives(run_build, corpus):
    path = corpus / ".git" / "info" / "exclude"
    path.write_text("# hand-written\nsecrets.env\n")
    run_build(corpus)
    assert path.read_text().splitlines() == ["# hand-written", "secrets.env", "graphify-out/"]


def test_a_commented_out_entry_does_not_count_as_excluded(run_build, corpus):
    path = corpus / ".git" / "info" / "exclude"
    path.write_text("# graphify-out/\n")
    run_build(corpus)
    assert "graphify-out/" in path.read_text().splitlines()


def test_a_linked_worktree_excludes_into_the_shared_common_dir(run_build, corpus, tmp_path):
    """A worktree's .git is a pointer file, and the exclude git reads lives in the shared dir."""
    subprocess.run(["git", "-C", str(corpus), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(corpus), "commit", "-qm", "init"], check=True,
                   capture_output=True)
    linked = tmp_path / "linked"
    subprocess.run(["git", "-C", str(corpus), "worktree", "add", "-q", str(linked), "-b", "side"],
                   check=True, capture_output=True)
    result, _ = run_build(linked)
    assert result.returncode == 0, result.stderr
    assert "graphify-out/" in (corpus / ".git" / "info" / "exclude").read_text().splitlines()


def test_git_being_absent_does_not_stop_the_build(run_build, corpus):
    """The local exclude is a courtesy; losing it must not cost the graph."""
    result, calls = run_build(corpus, PATH_STRIP_GIT="1")
    assert result.returncode == 0, result.stderr
    assert flags(calls, "extract"), "the build must still run without git"


def test_a_corpus_outside_git_still_builds(run_build, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("def f():\n    return 1\n")
    result, calls = run_build(plain)
    assert result.returncode == 0, result.stderr
    assert flags(calls, "extract")


# --- failure is reported, not swallowed ----------------------------------------

def test_a_path_that_does_not_exist_fails_before_spending_anything(run_build, tmp_path):
    result, calls = run_build(tmp_path / "nope")
    assert result.returncode != 0
    assert calls == []


def test_a_failed_extract_stops_short_of_labelling(run_build, corpus):
    result, calls = run_build(corpus, GRAPHIFY_SHIM_FAIL="extract")
    assert result.returncode != 0
    assert [c[0] for c in calls] == ["extract"]


def test_extract_that_writes_no_graph_is_caught(run_build, corpus):
    result, calls = run_build(corpus, GRAPHIFY_SHIM_NO_GRAPH="1")
    assert result.returncode != 0
    assert "label" not in [c[0] for c in calls]


def test_unnamed_communities_fail_the_build_rather_than_passing_quietly(run_build, corpus):
    result, _ = run_build(corpus, GRAPHIFY_SHIM_PLACEHOLDER="1")
    assert result.returncode != 0
    assert "1 of 2 communities are unnamed" in result.stderr


def test_a_fully_named_graph_reports_its_own_summary(run_build, corpus):
    result, _ = run_build(corpus)
    assert "build.py: 2 communities named" in result.stdout


def test_a_stale_graph_is_never_labelled(run_build, corpus):
    """extract can exit 0 without writing; the graph left behind is then the old one."""
    out = corpus / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({"nodes": [], "links": []}))
    result, calls = run_build(corpus, GRAPHIFY_SHIM_NO_GRAPH="1")
    assert result.returncode != 0
    assert "stale" in result.stderr
    assert "label" not in [c[0] for c in calls]


def test_a_failed_label_is_reported(run_build, corpus):
    result, _ = run_build(corpus, GRAPHIFY_SHIM_FAIL="label")
    assert result.returncode != 0


def test_labelling_that_writes_no_names_is_not_called_a_success(run_build, corpus):
    result, _ = run_build(corpus, GRAPHIFY_SHIM_NO_LABELS="1")
    assert result.returncode != 0
    assert "unnamed" in result.stderr


# --- the real thing ------------------------------------------------------------

@pytest.mark.integration
def test_real_graphify_builds_a_graph_with_edges(corpus):
    """Covers the code-only flags against the real CLI."""
    if subprocess.run(["which", "graphify"], capture_output=True).returncode != 0:
        pytest.skip("graphify CLI not installed")
    result = subprocess.run(
        ["python3", str(BUILD_PY), str(corpus)], capture_output=True, text=True, timeout=600
    )
    assert result.returncode == 0, result.stdout + result.stderr
    graph = json.loads((corpus / "graphify-out" / "graph.json").read_text())
    assert len(graph["links"]) > 0, "the fixture's two modules must produce a real edge"
    labels = json.loads((corpus / "graphify-out" / ".graphify_labels.json").read_text())
    assert labels and all(v for v in labels.values())
    status = subprocess.run(
        ["git", "-C", str(corpus), "status", "--porcelain"], capture_output=True, text=True
    )
    assert "graphify-out" not in status.stdout


@pytest.mark.integration
def test_real_semantic_build_reaches_the_claude_cli_backend(corpus):
    """The semantic flags are the ones most likely to drift, and the shim cannot see that."""
    for tool in ("graphify", "claude"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            pytest.skip(f"{tool} CLI not installed")
    result = subprocess.run(
        ["python3", str(BUILD_PY), str(corpus), "--semantic"],
        capture_output=True, text=True, timeout=900,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    graph = json.loads((corpus / "graphify-out" / "graph.json").read_text())
    sources = {n.get("source_file") for n in graph["nodes"]}
    assert "README.md" in sources, f"the doc was not indexed; sources were {sources}"
