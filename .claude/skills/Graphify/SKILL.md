---
name: Graphify
description: Answer questions about a codebase from a persistent graphify knowledge graph instead of repeated grep — build one, query it, trace impact through it, refresh it. Use when the repo has a graphify-out/ directory, when the user says graphify or asks for a code graph, or when a question spans enough of an unfamiliar codebase that grep would take many rounds ("how does X reach Y", "what breaks if I change Z", "what are the main pieces here"). Not for a repo with no graph unless the user agrees to build one first, and not for finding a string you already know, editing files, or running tests — ordinary search and the normal tools beat the graph at all three.
allowed-tools: Bash(graphify:*)
---

# Graphify

A graph of a codebase's symbols and how they reach each other, built once and reused, so a question costs a traversal instead of a scan.

`graphify --help` is the whole command inventory, one line each; read it rather than guessing at a command. What follows is only what the tool cannot say about itself.

## The one thing that will make you confidently wrong

`query` breaks your question into terms, drops the stopwords, and scores what is left against each node's label — exact, then prefix, then substring — plus a flat bonus if a term appears anywhere in the node's source path, weighting rarer terms more. It is forgiving about case and word order and completely literal about the words themselves: nothing is expanded into a synonym, a stem, or a translation.

`No matching nodes found.` means every node scored zero. That is one message for several different situations, and it does not tell you which:

- **Your words aren't its words.** Ask graphify's own source about `authentication` and you get nothing, in a codebase that holds API keys for six LLM providers — it calls them `detect_backend()`, `_call_claude()`, `_backend_pkg_hint()`.
- **That layer isn't in the graph.** What a build indexed depends on how it was run, and even a semantic pass can miss an entity it saw.
- **The graph predates the code.** It is a snapshot; nothing written since the last build is in it.
- **It genuinely isn't there** — the only conclusion the message looks like, and the last one you are entitled to.

The fixes are different for each, so rule the others out before you report an absence: check what the graph calls things, what it was built from, and when. `god-nodes` is the cheapest vocabulary probe there is — it hands back real symbol names, in the graph's own words, which is exactly what the matcher wants.

## Building

```
python3 "${CLAUDE_SKILL_DIR}/scripts/build.py" --help
```

That script owns the two-step contract and the flags, so don't assemble `extract` and `label` by hand. Three things behind it that no `--help` can tell you:

**`--backend claude-cli` is never chosen for you.** graphify picks a backend by looking for API keys, a local model server, or AWS credentials, and deliberately leaves `claude-cli` out of that search — so it is only ever used when named outright, which is why the script names it every time.

**Choose `--semantic` by what is being asked, not by what is in the repo.** Code-only parsing answers questions about structure: what calls what, what breaks, where the hubs are. Semantic extraction is what you need when the question is about *intent* — why something was built this way, what a design note decided.

**"N communities named" is not proof the LLM ran.** If every backend call fails, graphify says so on stderr and then names each community after its busiest symbol instead. The build still succeeds and the names are still usable, just blunter — and since community names are part of what `query` matches, missing that warning shows up much later as a graph that is harder to ask questions of.

The build keeps its output out of git by writing `graphify-out/` into the repo's local exclude file. That does nothing in a repo that already commits `graphify-out/` — there, a rebuild dirties tracked files, so check with the user before you start one.

Never write inline Python against the graphify package. It lives inside a `uv` tool's own interpreter and will not import from the system `python3`; every workaround for that is a layer you would then have to maintain. The CLI is the interface.

## Refreshing

Re-run `build.py` — there is no separate update ritual to remember and no reason to invent one. Two things the flags don't say: a code-only refresh over a graph that already has a semantic layer leaves that layer in place rather than deleting it, and `--force` is for when you suspect the graph disagrees with the tree, not for routine use.

`graphify-out/GRAPH_REPORT.md` is a good orientation document, and it grows with the repo — on anything real, reading it whole spends more than the graph saves. Its `##` headings tell you what sections exist — take the one you need.

## When the graph is the wrong tool

Reach for it when the question is about *relationships across the codebase*: reachability, impact, structure, orientation in unfamiliar code. That is what a traversal answers and what grep answers only by repetition.

Skip it when you already know the string you are looking for, when the answer sits in one file you could just open, or when you need the current text of code you are about to edit. The graph stores labels and edges, not file contents, and it is always as old as the last build. Read the file.
