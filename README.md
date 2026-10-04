# Six Schools Lab

**An Omnigent research lab that audits inherited taxonomies of thought: were the "schools" discovered, or invented later?**

Built for the 7th Hack-Nation Global AI Hackathon, Challenge 3 (Agentic Scientific Discovery, Databricks Omnigent).

Every field inherits its categories. Chinese textbooks sort the thinkers of the Warring States into "schools" (Confucian, Daoist, Legalist, ...) that were first written down by the historian Sima Tan around 100 BCE, one to three centuries after the texts. Western textbooks sort philosophers into "analytic" and "continental", a division that became standard only after the Second World War. Are such partitions structure that is already in the texts, or labels applied in hindsight?

A modern language model cannot answer this honestly, because it has memorized both the texts and the labels. The lab therefore runs two designs that the labels cannot leak into:

| | Taxonomy under audit | Time capsule | Logic |
|---|---|---|---|
| **Sealed text** | Sima Tan's six schools | The Mawangdui silk manuscripts ("Huangdi Sijing"), buried 168 BCE and never edited by the Han collators who compiled the transmitted books | The reader cannot be sealed, so test the taxonomy on a text sealed before the taxonomy existed |
| **Sealed reader** | Analytic vs continental | `talkie-1930`, a 13B language model trained only on text published before 1931 | The texts cannot be sealed, so read them with a reader sealed before the label existed |

**Live replay of the run:** https://duowenpu.github.io/six-schools-lab/demo/ (source in [`demo/`](demo/)). Full result tables: [`docs/RESULTS.md`](docs/RESULTS.md), generated from the research records.

## What the lab found

The study was run twice: run A on a fixed protocol, run B on another machine with the model vendors swapped, its own taxonomies and its own research record. The conclusion below was written by the planner agent, passed the auditor agent, and was published after human approval (record `r0166`, approval `r0167`). Scores are chance-corrected: 0 is luck, 1 is perfect.

| Pre-registered hypothesis | Verdict of the lab | Numbers |
|---|---|---|
| **H-C1** The six schools predict where an unseen book falls better than era, region or genre | **Refuted as pre-registered.** The six schools are well above chance but do not beat sorting by literary form in run A. The tie did not replicate in run B | Run A: six 0.354, form 0.336, region 0.259, era 0.100 (n.s.); on the modern translation form 0.354, six 0.327. Run B: six 0.486, form 0.261 |
| **H-C2** The instrument ranks chapters known to be Daoist-leaning high inside non-Daoist books | **Supported, replicated.** The only cleanly replicated substantive result; it validates the instrument, not the taxonomy | Mean percentile 95.4 (run A) and 95.0 (run B), p = 0.0001 |
| **H-C3** The sealed manuscript sits between two schools instead of falling cleanly into one | **Supported in run A by the pre-registered rule, not replicated in run B.** Not to be relied on | Dominant label share 0.588 (run A, threshold 0.70) and 0.824 (run B). The lab's skeptic showed the threshold is poorly calibrated: about 39% of ordinary books also fall below it |
| **H-W1** A reader sealed in 1930 already separates analytic from continental | **Not supported as pre-registered.** The 1930 reader does separate them above chance, but "translated or written in English" explains the result at least as well | Analytic / continental 0.317 (p = 0.0015); translated or not 0.755. Run B: 0.529 and 0.755. Restricted to authors who wrote in English (run B): 0.416, p = 0.0025, 14 authors |
| **H-W2** A modern reader separates the later label more sharply than the 1930 reader (hindsight gap) | **Not testable as designed**; the interval includes zero in both runs | G = 0.024, 95% CI -0.028 to 0.078 (run A); G = 0.016, 95% CI -0.046 to 0.077 (run B) |

Six of eight headline findings replicate across the two runs. The two that do not (six schools against literary form; the tomb test verdict) both depend on how a taxonomy is coded onto the books, which the lab reports as its main limitation. The recognition probe shows why the sealed designs are needed: with names masked, one blind reader still named the source book of 35 of 35 passages.

## What the agents do, and what was built for them

The discovery loop is carried out by Omnigent agents running on two model vendors (qwen3.8-max and glm-5.3) and two harnesses (Claude Agent SDK and Codex):

1. **Question and pre-registration** (human): objective, five hypotheses with decision thresholds, decision rules, and an experiment budget of 16 credits are written into the research record before the first session ([`records/preregistration.json`](records/preregistration.json)).
2. **Evidence and rival hypotheses** (advocates, historian): advocates search the literature (OpenAlex, Wikipedia), formalize *rival* taxonomies as labellings with one citation per label, and freeze them. A frozen taxonomy can never be changed. Sealed units cannot be labelled.
3. **Experiment** (statistician): a tournament. Leave one book out and ask whether its passages fall nearest to the other books sharing its label. Null: book-level label permutation.
4. **Critique** (skeptic): the strongest alternative explanations, each with a concrete control.
5. **Decision gate** (planner): at least three candidate follow-up experiments are compared by expected learning, feasibility and cost; the planner chooses under the remaining credits and applies the pre-registered decision rules.
6. **Result and updated decision**: instrument validation, the tomb test, the style control, the recognition probe; then the second line with the sealed reader and the hindsight gap.
7. **Publication** is blocked by policy until the instrument has passed validation, and then pauses for human approval.

The lab's equipment was written before the run and contains no scientific choices that depend on results: corpus builders, the embedding instrument, the statistics module, the tools and the policies. A pipeline smoke test with a throwaway labelling was run during tool development and is disclosed in the record; it is not a reported result. Every taxonomy, experiment choice, run, critique and conclusion in [`records/research_record.jsonl`](records/research_record.jsonl) comes from the agents.

## Agents

| Agent | Model · harness | Scientific decision it owns | Tools | Role in the challenge brief |
|---|---|---|---|---|
| `planner` | qwen3.8-max · claude-sdk | Which experiment runs next under the budget; when a result reopens an assumption; when to ask the human | sub-agent dispatch, `record_append`, `record_read`, `list_experiments`, `request_publication` | Experiment planner |
| `advocate_a` | qwen3.8-max · claude-sdk | How one rival taxonomy maps onto the corpus | `corpus_info`, `openalex_search`, `wikipedia_lookup`, `submit_taxonomy` | Insight agent |
| `advocate_b` | glm-5.3 · codex | Same, on a different vendor and harness | same | Insight agent |
| `historian` | glm-5.3 · codex | Whether a background claim is supported | `openalex_search`, `wikipedia_lookup`, `check_citation` | Literature agent |
| `statistician` | qwen3.8-max · claude-sdk | How a result is read; the only agent that can run experiments | `run_experiment`, `list_experiments` | Experiment runner, Analysis agent |
| `skeptic` | glm-5.3 · claude-sdk | Which objections must be answered | read-only record and taxonomies | Analysis agent |
| `auditor` | glm-5.3 · claude-sdk | Whether claims are sourced and not overstated | `check_citation`, read-only record | Safety agent |
| `prober_a`, `prober_b` | qwen3.8-max, glm-5.3 | none (blind readers) | `get_blind_batch`, `submit_probe` only | part of the experiment |
| research record | — | — | append-only, hash-chained, entries linked by id | Knowledge graph agent |

Agent specifications: [`lab/bundle/`](lab/bundle/) (generated by [`lab/build_bundle.py`](lab/build_bundle.py) from [`lab/prompts/`](lab/prompts/)).

## Policies and tool permissions

The controls of the experiment are enforced by the orchestration layer, not by asking models to behave. Policy code: [`labtools/policies.py`](labtools/policies.py). Log of every DENY and ASK: [`records/policy_log.jsonl`](records/policy_log.jsonl).

| # | Control | Mechanism |
|---|---|---|
| P1 | Blind readers see masked passages only | No agent declares `os_env`, so none has file or shell tools. A `tool_call` allowlist policy per agent denies every tool that is not on its list, including harness-native tools |
| P2 | Hypotheses are fixed before data | `submit_taxonomy` freezes and hashes a taxonomy; `run_experiment` refuses unfrozen taxonomies and refuses to run without a pre-registration entry |
| P3 | Instrument gate | `request_publication` is denied until the pre-registered validation test has passed |
| P4 | Budget | 16 experiment credits enforced by `run_experiment`; Omnigent `cost_budget` asks the human at spend checkpoints; a per-session tool-call cap |
| P5 | Human approval | `request_publication` returns ASK and waits for a human in the Omnigent UI |
| P6 | Attribution | Each agent has its own copy of every tool with its name baked in, so record entries are attributed by the bundle, not self-reported |

## Instruments

| Instrument | Understands meaning | Knows later labels | Used for |
|---|---|---|---|
| `lex`: TF-IDF of character bigrams (Chinese) or word 1-2-grams (English), names masked | no | no | both lines |
| `lex_tr`: the same on the modern-Chinese translation | no | no | style control |
| `qwen`: mean-pooled hidden states of Qwen3-14B-Base | yes | yes | modern reader |
| `talkie`: mean-pooled hidden states of talkie-1930-13b-base | yes | no, for labels coined after 1930 | sealed reader |

Both reader models run locally and offline in a container (`--network none`), full precision (bf16), with the same script: [`instruments/embed.py`](instruments/embed.py).

## Reproduce

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt
git clone --depth 1 --filter=blob:none --sparse https://github.com/NiuTrans/Classical-Modern.git data_raw/Classical-Modern
git -C data_raw/Classical-Modern sparse-checkout set "双语数据"
.venv/bin/python corpus/build_zh.py        # 25 books, 1,101 passages
.venv/bin/python corpus/build_en.py        # 25 authors, 55 books, 3,209 passages (Project Gutenberg)
# embeddings (GPU, offline): python instruments/embed.py --model <path> --inp corpus/en/blind.jsonl --out out/en_talkie.npz
.venv/bin/python analysis/cli.py tournament '{"taxonomy_id": "six", "instrument": "lex"}'
```

To run the lab itself: install [Omnigent](https://github.com/omnigent-ai/omnigent), make this repository importable by its Python environment, configure two model providers, then

```bash
.venv/bin/python lab_init.py               # human step: objective + pre-registration into the record
omnigent run lab/bundle -p "$(cat lab/kickoff_phase1.txt)"
```

## Data and licences

- Early Chinese corpus: [NiuTrans/Classical-Modern](https://github.com/NiuTrans/Classical-Modern) (MIT), classical text with aligned modern-Chinese translation. Provenance and hashes: `corpus/zh/provenance.json`.
- English corpus: Project Gutenberg, works published before 1931. Provenance and hashes: `corpus/en/provenance.json`.
- Readers: [talkie-1930-13b-base](https://huggingface.co/talkie-lm/talkie-1930-13b-base) (Apache-2.0; BF16 Transformers conversion by xlr8harder) and [Qwen3-14B-Base](https://huggingface.co/Qwen/Qwen3-14B-Base).

## Limitations

- Few independent units: 23 transmitted books and 25 authors. Classes with a single unit cannot be tested out of sample and are reported as untestable.
- The sealed manuscript is short, and its identification and dating are themselves disputed.
- Continental authors are read in English translation; a "translated vs original" taxonomy is included as a confound control but cannot remove the confound.
- The 1930 reader has read these very books. It is sealed against later labels, not against the texts.
- The instrument only sees vocabulary or pooled hidden states. It cannot weigh arguments.
- Labels come from language-model agents reading secondary sources. Citations are checked for resolution and relevance by the auditor, not for scholarly quality.

## Validation still needed before anyone should rely on this

More excavated manuscripts (Guodian, Shanghai Museum slips), blind labelling by domain experts, several sealed readers with different cut-off years, and replication on other corpora.

## Measured acceleration and the path to 10x

The bottleneck attacked here is the path from a claim in the literature to an executed, controlled test of that claim against its rivals. Measured in run A ([`out/acceleration.json`](out/acceleration.json)):

| Measure | Value |
|---|---|
| Net wall-clock time of the run | 2.73 h (3.59 h gross, 0.86 h infrastructure downtime) |
| Rival taxonomies formalized with one citation per label | 11 (4.0 per hour) |
| Controlled tests run | 15 (5.5 per hour) |
| One taxonomy: human against agent | 14.6 min (one person, single timed trial, [`records/human_baseline_region.csv`](records/human_baseline_region.csv)) against a median of 10.5 min per agent (n = 9): **1.4x** |
| Four taxonomies: one person in sequence against agents in parallel | about 58.5 min (extrapolated) against 16.8 min: **3.5x** |
| From a skeptic critique to the next executed test | 9.2, 13.9 and 29.5 min |

The measured gain is modest for a single task and comes mostly from parallel work and from the short loop between critique and test. The path to 10x is more advocates and statisticians in parallel on a larger corpus; the human stays at pre-registration and at the approval gate. Caveats: one corpus, a single human trial, and agent labels are checked for citation resolution, not for scholarly quality.
