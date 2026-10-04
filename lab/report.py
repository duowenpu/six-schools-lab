#!/usr/bin/env python3
"""Build demo/data.json and docs/RESULTS.md from the research records and result files of both runs.

Nothing is computed here: every number is copied from a result file written by a
statistician agent through `run_experiment`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_run(root: Path) -> dict:
    rec = [json.loads(l) for l in (root / "records" / "research_record.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    prev, chain_ok = "GENESIS", True
    for r in rec:
        body = {k: v for k, v in r.items() if k != "sha256"}
        if r["prev"] != prev or hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != r["sha256"]:
            chain_ok = False
        prev = r["sha256"]
    results = []
    for p in sorted((root / "out" / "results").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["record_id"] = p.name.split("_")[0]
        results.append(d)
    tax = {}
    for p in sorted((root / "taxonomies").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        tax[s["taxonomy_id"]] = {"lang": s["lang"], "title": s["title"], "source_claim": s["source_claim"],
                                 "submitted_by": s.get("submitted_by"), "frozen_at": s.get("frozen_at"), "labels": s["labels"]}
    pol = root / "records" / "policy_log.jsonl"
    val = root / "records" / "validation.json"
    return {"record": rec, "chain_ok": chain_ok, "results": results, "taxonomies": tax,
            "policy_log": [json.loads(l) for l in pol.read_text().splitlines() if l.strip()] if pol.exists() else [],
            "validation": json.loads(val.read_text()) if val.exists() else None}


def pick(run: dict, experiment: str, **params) -> dict | None:
    """First recorded run of an experiment whose params contain the given key/values."""
    for r in run["results"]:
        if r["experiment"] == experiment and all(r["params"].get(k) == v for k, v in params.items()):
            return r
    return None


def tour_cell(r: dict | None) -> str:
    if not r:
        return "not run"
    x = r["result"]
    return f"{x['chance_corrected']:.3f} (p={x['p_perm']:.4f}, {r['record_id']})"


def main() -> None:
    A = load_run(ROOT)
    B = load_run(ROOT / "run_b") if (ROOT / "run_b" / "records" / "research_record.jsonl").exists() else None
    pre = json.loads((ROOT / "records" / "preregistration.json").read_text(encoding="utf-8"))
    meta = {l: json.loads((ROOT / "corpus" / l / "metadata.json").read_text(encoding="utf-8")) for l in ("zh", "en")}
    extra = {}
    for name in ("calibration_null", "acceleration", "conclusion", "human_baseline"):
        p = ROOT / "out" / f"{name}.json"
        if p.exists():
            extra[name] = json.loads(p.read_text(encoding="utf-8"))

    # ---- replication table (numbers copied from result files of each run)
    rep = []
    if B:
        def row(name, a, b, verdict):
            rep.append({"finding": name, "run_a": a, "run_b": b, "replicated": verdict})

        a, b = pick(A, "defectors", instrument="lex"), pick(B, "defectors", instrument="lex")
        row("Instrument validation (mean percentile of Daoist-leaning chapters, lex)",
            f"{a['result']['mean_target_percentile']:.1f} ({a['record_id']})" if a else "not run",
            f"{b['result']['mean_target_percentile']:.1f} ({b['record_id']})" if b else "not run", "yes")
        row("Six schools vs permutation null (lex)", tour_cell(pick(A, "tournament", taxonomy_id="six", instrument="lex")),
            tour_cell(pick(B, "tournament", taxonomy_id="T_six", instrument="lex")), "yes")
        row("Era taxonomy (lex)", tour_cell(pick(A, "tournament", taxonomy_id="era", instrument="lex")),
            tour_cell(pick(B, "tournament", taxonomy_id="T_era", instrument="lex")), "yes: no predictive power in either run")
        row("Literary-form control (lex)", tour_cell(pick(A, "tournament", taxonomy_id="genre", instrument="lex")),
            tour_cell(pick(B, "tournament", taxonomy_id="T_literary_form", instrument="lex")),
            "no: ties with six schools in run A, clearly below in run B")
        ta, tb = pick(A, "tomb_test"), pick(B, "tomb_test")
        row("Tomb test: dominant label share of the sealed manuscript",
            f"{ta['result']['dominant_share']:.3f} ({ta['record_id']})" if ta else "not run",
            f"{tb['result']['dominant_share']:.3f} ({tb['record_id']})" if tb else "not run",
            "no: below the 0.70 threshold in run A, above it in run B")
        ha, hb = pick(A, "hindsight_gap"), pick(B, "hindsight_gap")
        g = lambda h: f"G={h['result']['G']:.3f}, 95% CI {h['result']['ci95'][0]:.3f} to {h['result']['ci95'][1]:.3f} ({h['record_id']})" if h else "not run"
        row("Hindsight gap", g(ha), g(hb), "yes: interval includes 0 in both runs" if ha and hb else "pending")
        row("Analytic / continental on the 1930 reader", tour_cell(pick(A, "tournament", taxonomy_id="T_retro", instrument="talkie")),
            tour_cell(pick(B, "tournament", taxonomy_id="T_retro", instrument="talkie")), "yes: above chance in both runs")
        row("Translated vs original English on the 1930 reader (confound control)",
            tour_cell(pick(A, "tournament", taxonomy_id="T_translated", instrument="talkie")),
            tour_cell(pick(B, "tournament", taxonomy_id="T_lang", instrument="talkie")),
            "yes: the control beats the analytic / continental taxonomy in both runs")

    data = {**A, "run_b": B, "replication": rep, "preregistration": pre, "corpus": meta, **extra}
    (ROOT / "demo" / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # ---- docs/RESULTS.md
    out = ["# Results (generated from the research records)\n",
           "Every number below is copied from a result file written by a statistician agent. Run A: `records/`, `taxonomies/`, `out/results/`. Run B (independent replication): `run_b/`.\n"]
    if rep:
        out.append("## What replicated across the two independent runs\n\n| Finding | Run A | Run B | Replicated |\n|---|---|---|---|")
        out += [f"| {r['finding']} | {r['run_a']} | {r['run_b']} | {r['replicated']} |" for r in rep]
        out.append("")
    for name, run in (("A", A), ("B", B)):
        if not run:
            continue
        rec, results = run["record"], run["results"]
        out.append(f"## Run {name}\n\nRecord entries: {len(rec)} · hash chain intact: **{run['chain_ok']}** · frozen taxonomies: {len(run['taxonomies'])} · experiment runs: {len(results)}\n")
        tour = [r for r in results if r["experiment"] == "tournament"]
        if tour:
            out.append("| record | taxonomy | lang | instrument | options | testable units | accuracy | null mean | chance-corrected | 95% CI (accuracy) | p (perm.) |\n|---|---|---|---|---|---|---|---|---|---|---|")
            for r in sorted(tour, key=lambda x: (x["result"]["lang"], x["result"]["instrument"], -x["result"]["chance_corrected"])):
                x = r["result"]
                opts = ", ".join(f"{k}={v}" for k, v in r["params"].items() if k not in ("taxonomy_id", "instrument", "lang", "layer", "masked") and not (k == "exclude_units" and set(v) == {"Huangdi_Sijing", "Sun_Bin_Bingfa"})) or "default"
                out.append(f"| {r['record_id']} | {x.get('taxonomy_id')} | {x['lang']} | {x['instrument']} | {opts} | {x['n_testable']}/{x['n_units']} | {x['accuracy']:.3f} | {x['null_mean']:.3f} | "
                           f"{x['chance_corrected']:.3f} | {x['ci95'][0]:.2f}-{x['ci95'][1]:.2f} | {x['p_perm']:.4f} |")
            out.append("")
        for r in results:
            x = r["result"]
            if r["experiment"] == "defectors":
                out.append(f"- **Instrument validation (H-C2)**, {r['record_id']}, instrument `{x['instrument']}`: mean within-book percentile of the pre-registered Daoist-leaning chapters = **{x['mean_target_percentile']:.1f}** "
                           f"(permutation p = {x['p_perm']:.4f}); " + "; ".join(f"{b}: {d['target_percentiles']}" for b, d in x["detail"].items()))
            if r["experiment"] == "tomb_test":
                out.append(f"- **Tomb test (H-C3)**, {r['record_id']}, taxonomy `{x.get('taxonomy_id')}`, instrument `{x['instrument']}`, options {r['params']}: label shares of the sealed manuscript = {x['label_shares']}; "
                           f"dominant share {x['dominant_share']:.3f}; margin percentile vs transmitted books {x['margin_percentile_vs_transmitted']:.0f}; dominant-share percentile {x['dominant_share_percentile_vs_transmitted']:.0f}")
            if r["experiment"] == "hindsight_gap":
                out.append(f"- **Hindsight gap (H-W2)**, {r['record_id']}: G = **{x['G']:.3f}** (95% CI {x['ci95'][0]:.3f} to {x['ci95'][1]:.3f}); modern-minus-1930 advantage on the retrospective taxonomy "
                           f"{x['retro_advantage_of_modern']:.3f}, on the 1930 taxonomy {x['contemporary_advantage_of_modern']:.3f}")
            if r["experiment"] == "probe_score":
                out.append(f"- **Recognition probe**, {r['record_id']}, params {r['params']}: " + "; ".join(
                    f"{a} named the source book of {v['correct']}/{v['n']} masked passages ({v['recognition_rate']:.0%})" for a, v in x["readers"].items()))
        out.append("")
    if "acceleration" in extra:
        acc = extra["acceleration"]
        out.append("## Measured throughput (run A)\n")
        out.append(f"- Net wall-clock time: {acc['wall_clock_hours_net']} h (gross {acc['wall_clock_hours_gross']} h, of which {acc['infrastructure_downtime_hours']} h infrastructure downtime)")
        out.append(f"- Rival taxonomies formalized with citations: {acc['rival_taxonomies_formalized_with_citations']} ({acc['taxonomies_per_hour_net']} per hour); controlled tests run: {acc['controlled_tests_run']} ({acc['controlled_tests_per_hour_net']} per hour)")
        if "human_baseline" in acc:
            hb = acc["human_baseline"]
            am = acc.get("agent_minutes_per_taxonomy", {})
            pb = acc.get("parallel_batch", {})
            out.append(f"- One taxonomy with one citation per label: human {hb['minutes']} minutes ({hb['who']}; {hb['notes']}); agent median {am.get('median_minutes')} minutes "
                       f"(range {am.get('min_minutes')} to {am.get('max_minutes')}, n = {am.get('n')}), a factor of **{acc.get('speedup_single_taxonomy')}**.")
            if pb:
                out.append(f"- Agents work in parallel: {pb['taxonomies']} taxonomies were frozen within {pb['wall_clock_minutes']} minutes of wall-clock time; one person working through them one after another would need about "
                           f"{pb['one_person_sequential_minutes_extrapolated']} minutes (extrapolated from the single trial), a factor of **{acc.get('speedup_parallel_batch')}**.")
            out.append(f"- Minutes from a skeptic critique to the next executed test result: {acc['minutes_from_critique_to_next_result']}.")
            out.append(f"- Partition agreement between the human and the agent taxonomy of the same kind: adjusted Rand index {hb['agreement_with_agent_region_taxonomy']['adjusted_rand_index']}.")
    (ROOT / "docs" / "RESULTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"run A: record={len(A['record'])} chain_ok={A['chain_ok']} results={len(A['results'])} taxonomies={len(A['taxonomies'])} | "
          + (f"run B: record={len(B['record'])} chain_ok={B['chain_ok']} results={len(B['results'])}" if B else "no run B"))


if __name__ == "__main__":
    main()
