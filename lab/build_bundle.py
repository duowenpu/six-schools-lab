#!/usr/bin/env python3
"""Generate the Omnigent agent bundle (lab/bundle/) from one source of truth.

Omnigent registers bundle-local Python tools by file name, one tool per file,
so every agent directory gets its own thin wrapper files. Each wrapper has the
agent's name baked in as ACTOR, which is how the research record attributes
entries without trusting a model's self-report.
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "bundle"

# tool name -> (signature, docstring body, call expression)
TOOLS = {
    "record_append": ("type: str, payload_json: str, links: str = \"\"",
                      "Append one entry to the shared, hash-chained research record.\n\n"
                      ":param type: One of objective, evidence, critique, candidate_experiments, decision, approval_request, audit, next_experiment, note.\n"
                      ":param payload_json: JSON object with the content, e.g. ``{\"claim\": \"...\", \"sources\": [\"https://...\"]}``.\n"
                      ":param links: Comma-separated ids of related record entries, e.g. ``\"r0004,r0007\"``.\n"
                      ":returns: JSON with the new entry id.",
                      "core.record_append(ACTOR, type, payload_json, links, hypothesis_origin=\"agent\")"),
    "record_read": ("last_n: int = 20, type: str = \"\", actor: str = \"\"",
                    "Read recent entries of the shared research record.\n\n"
                    ":param last_n: How many entries to return, e.g. ``20``.\n"
                    ":param type: Optional filter, e.g. ``\"result\"`` or ``\"taxonomy_frozen\"``.\n"
                    ":param actor: Optional filter by agent name, e.g. ``\"statistician\"``.\n"
                    ":returns: JSON list of entries.",
                    "core.record_read(last_n, type, actor)"),
    "list_experiments": ("",
                         "List the experiments the lab can run, their credit costs, credits left, and the pre-registered hypotheses.\n\n"
                         ":returns: JSON object.",
                         "core.list_experiments()"),
    "list_taxonomies": ("",
                        "List all frozen taxonomies (id, language, title, classes).\n\n:returns: JSON list.",
                        "core.list_taxonomies()"),
    "read_taxonomy": ("taxonomy_id: str",
                      "Read one frozen taxonomy with all labels, confidences and citations.\n\n"
                      ":param taxonomy_id: e.g. ``\"T_six\"``.\n:returns: JSON object.",
                      "core.read_taxonomy(taxonomy_id)"),
    "corpus_info": ("lang: str",
                    "List the corpus units that a taxonomy can label (no labels, no results).\n\n"
                    ":param lang: ``\"zh\"`` (early Chinese books) or ``\"en\"`` (pre-1931 philosophy authors).\n:returns: JSON object.",
                    "core.corpus_info(lang)"),
    "submit_taxonomy": ("taxonomy_json: str",
                        "Validate and FREEZE a taxonomy so it can be tested. A frozen taxonomy can never be changed.\n\n"
                        ":param taxonomy_json: JSON with taxonomy_id, lang, title, source_claim, labels "
                        "(``{unit: {\"label\": str|null, \"confidence\": \"high|medium|contested\", \"citation\": url|\"uncertain\", \"note\": str}}``).\n"
                        ":returns: JSON with sha256 and record id, or validation problems to fix.",
                        "core.submit_taxonomy(ACTOR, taxonomy_json)"),
    "run_experiment": ("experiment: str, params_json: str = \"{}\"",
                       "Run one registered experiment on frozen taxonomies. Costs credits; refused when the budget is spent.\n\n"
                       ":param experiment: e.g. ``\"tournament\"``, ``\"defectors\"``, ``\"tomb_test\"``, ``\"hindsight_gap\"``, ``\"corpus_map\"``, ``\"probe_score\"``.\n"
                       ":param params_json: JSON parameters, e.g. ``{\"taxonomy_id\": \"T_six\", \"instrument\": \"lex\"}``.\n"
                       ":returns: JSON with record ids, credits left and the result summary.",
                       "core.run_experiment(ACTOR, experiment, params_json)"),
    "get_blind_batch": ("batch_id: int",
                        "Get one batch of masked passages for the recognition probe.\n\n:param batch_id: e.g. ``0``.\n:returns: JSON with passages.",
                        "core.get_blind_batch(batch_id)"),
    "submit_probe": ("batch_id: int, guesses_json: str",
                     "Submit source guesses for one batch.\n\n:param batch_id: e.g. ``0``.\n"
                     ":param guesses_json: JSON list of ``{\"id\": ..., \"guess_book\": ..., \"confidence\": 0.0-1.0}``.\n:returns: JSON.",
                     "core.submit_probe(ACTOR, batch_id, guesses_json)"),
    "openalex_search": ("query: str",
                        "Search scholarly literature (OpenAlex). Use the returned URLs as citations.\n\n"
                        ":param query: e.g. ``\"Sima Tan six schools\"``.\n:returns: JSON with titles, years, authors, venues, URLs.",
                        "core.openalex_search(query)"),
    "wikipedia_lookup": ("title: str, lang: str = \"en\"",
                         "Fetch the plain-text extract of a Wikipedia article and its URL.\n\n"
                         ":param title: Article title, e.g. ``\"Guanzi (text)\"``.\n:param lang: ``\"en\"`` or ``\"zh\"``.\n:returns: JSON.",
                         "core.wikipedia_lookup(title, lang)"),
    "check_citation": ("url: str",
                       "Fetch a citation URL and report HTTP status and page title.\n\n:param url: e.g. ``\"https://doi.org/10.2307/3096138\"``.\n:returns: JSON.",
                       "core.check_citation(url)"),
    "request_publication": ("conclusion_json: str",
                            "Publish the lab's conclusion. Blocked by policy until instrument validation passed; then a human must approve.\n\n"
                            ":param conclusion_json: JSON with findings per hypothesis (numbers + record ids), limitations, validation still needed, next experiment.\n:returns: JSON.",
                            "core.request_publication(ACTOR, conclusion_json)"),
}

WRAPPER = '''"""Lab tool `{name}` (generated by lab/build_bundle.py; do not edit)."""

from __future__ import annotations

import json

from omnigent_client.tools import tool

ACTOR = "{actor}"


@tool
def {name}({sig}) -> str:
    """
{doc}
    """
    from labtools import core

    return json.dumps({call}, ensure_ascii=False)
'''

AGENTS = {
    "advocate_a": dict(harness="claude-sdk", provider="Aliyun-Claude", prompt="advocate",
                       tools=["corpus_info", "openalex_search", "wikipedia_lookup", "submit_taxonomy", "read_taxonomy", "list_taxonomies", "record_append"],
                       desc="Advocate A - formalizes one rival taxonomy per dispatch from the literature and freezes it (qwen)."),
    "advocate_b": dict(harness="codex", provider="z.ai-openai", prompt="advocate",
                       tools=["corpus_info", "openalex_search", "wikipedia_lookup", "submit_taxonomy", "read_taxonomy", "list_taxonomies", "record_append"],
                       desc="Advocate B - formalizes one rival taxonomy per dispatch from the literature and freezes it (glm, different vendor and harness)."),
    "historian": dict(harness="codex", provider="z.ai-openai", prompt="historian",
                      tools=["openalex_search", "wikipedia_lookup", "check_citation", "record_append", "record_read"],
                      desc="Historian - verifies background claims against sources and records the evidence."),
    "statistician": dict(harness="claude-sdk", provider="Aliyun-Claude", prompt="statistician",
                         tools=["list_experiments", "run_experiment", "list_taxonomies", "read_taxonomy", "record_read", "record_append"],
                         desc="Statistician - the only agent that can run experiments; reads effect sizes and uncertainty."),
    "skeptic": dict(harness="claude-sdk", provider="z.ai", prompt="skeptic",
                    tools=["record_read", "list_taxonomies", "read_taxonomy", "list_experiments", "record_append"],
                    desc="Skeptic - tries to break the current result and proposes controls (different vendor than the planner)."),
    "auditor": dict(harness="claude-sdk", provider="z.ai", prompt="auditor",
                    tools=["record_read", "list_taxonomies", "read_taxonomy", "check_citation", "record_append"],
                    desc="Auditor - safety and integrity role: checks citations, flags overclaims, signs off before publication."),
    "prober_a": dict(harness="claude-sdk", provider="Aliyun-Claude", prompt="prober", tools=["get_blind_batch", "submit_probe"],
                     desc="Blind reader A - sees only masked passages (qwen)."),
    "prober_b": dict(harness="claude-sdk", provider="z.ai", prompt="prober", tools=["get_blind_batch", "submit_probe"],
                     desc="Blind reader B - sees only masked passages (glm)."),
}
# Reasoning effort per agent: long extended thinking was the main cost in wall-clock time.
EFFORT = {"statistician": "low", "auditor": "low", "prober_a": "low", "prober_b": "low"}
# Omnigent lifecycle events that reach the tool_call policy phase and must pass for a child session to start.
LIFECYCLE = ["sys_agent_start"]
PLANNER_TOOLS = ["record_append", "record_read", "list_experiments", "list_taxonomies", "corpus_info", "request_publication"]

CHILD_CFG = '''spec_version: 1
name: {name}
description: >-
  {desc}

executor:
  type: omnigent
  reasoning_effort: {effort}
  auth:
    type: provider
    name: {provider}
  config:
    harness: {harness}

# No os_env: this agent has no file or shell tools. It can only act through the
# lab tools in tools/python/ (tool permissions), and the allowlist policy below
# denies everything else, including harness-native tools.
guardrails:
  policies:
    tool_allowlist:
      type: function
      on:
        - tool_call
      function:
        path: labtools.policies.make_allowlist
        arguments:
          agent: {name}
          allowed: [{allowed}]
    tool_call_cap:
      type: function
      function:
        path: omnigent.policies.builtins.safety.max_tool_calls_per_session
        arguments:
          limit: 120

prompt: |
{prompt}
'''

PLANNER_CFG = '''spec_version: 1
name: six-schools-lab
description: >-
  Six Schools Lab - an agentic research lab that audits inherited taxonomies of
  thought with two leak-free designs: a sealed text and a sealed reader. The
  planner allocates a fixed experiment budget, delegates to specialist agents
  and keeps a hash-chained research record.

executor:
  type: omnigent
  reasoning_effort: medium
  auth:
    type: provider
    name: Aliyun-Claude
  config:
    harness: claude-sdk

async: true
cancellable: true

tools:
  agents:
{agents}

# P3 and P5 are enforced here, in the orchestration layer:
#  - no conclusion is published unless the instrument passed its validation test;
#  - publication always pauses for human approval.
# P4: spend checkpoints ask the human before the session continues.
guardrails:
  policies:
    instrument_gate:
      type: function
      on:
        - tool_call
      function:
        path: labtools.policies.make_instrument_gate
        arguments:
          tool: request_publication
    human_approval:
      type: function
      on:
        - tool_call
      function:
        path: labtools.policies.make_human_approval
        arguments:
          tools: [request_publication]
    spend_checkpoints:
      type: function
      function:
        path: omnigent.policies.builtins.cost.cost_budget
        arguments:
          max_cost_usd: 40.0
          ask_thresholds_usd: [15.0, 30.0]
          expensive_models: []

prompt: |
{prompt}
'''


# Run B: an independent, self-directed lab with the model vendors swapped (all on the claude-sdk harness).
VARIANT_B = {"planner_prompt": "planner_b", "planner_provider": "z.ai",
             "providers": {"advocate_a": "z.ai", "advocate_b": "Aliyun-Claude", "historian": "Aliyun-Claude",
                           "statistician": "z.ai", "skeptic": "Aliyun-Claude", "auditor": "Aliyun-Claude",
                           "prober_a": "Aliyun-Claude", "prober_b": "z.ai"}}


def main() -> None:
    import sys

    global OUT
    variant = sys.argv[1] if len(sys.argv) > 1 else "a"
    planner_prompt, planner_provider = "planner", "Aliyun-Claude"
    if variant == "b":
        OUT = HERE / "bundle_b"
        planner_prompt, planner_provider = VARIANT_B["planner_prompt"], VARIANT_B["planner_provider"]
        for name, prov in VARIANT_B["providers"].items():
            AGENTS[name] = dict(AGENTS[name], provider=prov, harness="claude-sdk")
    prompts = {p.stem: p.read_text(encoding="utf-8") for p in (HERE / "prompts").glob("*.md")}
    if OUT.exists():
        shutil.rmtree(OUT)

    def write_tools(d: Path, actor: str, names: list[str]) -> None:
        t = d / "tools" / "python"
        t.mkdir(parents=True)
        for n in names:
            sig, doc, call = TOOLS[n]
            (t / f"{n}.py").write_text(WRAPPER.format(name=n, actor=actor, sig=sig, call=call,
                                                      doc=textwrap.indent(doc, "    ")), encoding="utf-8")

    write_tools(OUT, "planner", PLANNER_TOOLS)
    (OUT / "config.yaml").write_text(PLANNER_CFG.format(
        agents="\n".join(f"    - {a}" for a in AGENTS), prompt=textwrap.indent(prompts[planner_prompt].strip(), "  ")
    ).replace("    name: Aliyun-Claude", f"    name: {planner_provider}").replace(
        "name: six-schools-lab\n", f"name: six-schools-lab{'-b' if variant == 'b' else ''}\n"), encoding="utf-8")
    for name, a in AGENTS.items():
        d = OUT / "agents" / name
        write_tools(d, name, a["tools"])
        (d / "config.yaml").write_text(CHILD_CFG.format(
            name=name, desc=a["desc"], provider=a["provider"], harness=a["harness"], effort=EFFORT.get(name, "medium"),
            allowed=", ".join(a["tools"] + LIFECYCLE), prompt=textwrap.indent(prompts[a["prompt"]].strip(), "  ")), encoding="utf-8")
    print("bundle written to", OUT, "agents:", ", ".join(AGENTS))


if __name__ == "__main__":
    main()
