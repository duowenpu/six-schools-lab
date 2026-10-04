#!/usr/bin/env python3
"""Build demo/data.json and docs/RESULTS.md from the research record and result files.

Nothing is computed here: every number is copied from a result record written
by the statistician agent through `run_experiment`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rec = [json.loads(l) for l in (ROOT / "records" / "research_record.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    # verify the hash chain
    prev, chain_ok = "GENESIS", True
    for r in rec:
        body = {k: v for k, v in r.items() if k != "sha256"}
        if r["prev"] != prev or hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != r["sha256"]:
            chain_ok = False
        prev = r["sha256"]
    results = []
    for p in sorted((ROOT / "out" / "results").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["record_id"] = p.name.split("_")[0]
        results.append(d)
    tax = {}
    for p in sorted((ROOT / "taxonomies").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        tax[s["taxonomy_id"]] = {"lang": s["lang"], "title": s["title"], "source_claim": s["source_claim"],
                                 "submitted_by": s.get("submitted_by"), "frozen_at": s.get("frozen_at"), "labels": s["labels"]}
    pol_path = ROOT / "records" / "policy_log.jsonl"
    policy = [json.loads(l) for l in pol_path.read_text().splitlines() if l.strip()] if pol_path.exists() else []
    pre = json.loads((ROOT / "records" / "preregistration.json").read_text(encoding="utf-8"))
    val_path = ROOT / "records" / "validation.json"
    meta = {l: json.loads((ROOT / "corpus" / l / "metadata.json").read_text(encoding="utf-8")) for l in ("zh", "en")}
    extra = {}
    for name in ("calibration_null", "acceleration", "conclusion"):
        p = ROOT / "out" / f"{name}.json"
        if p.exists():
            extra[name] = json.loads(p.read_text(encoding="utf-8"))
    data = {"record": rec, "chain_ok": chain_ok, "results": results, "taxonomies": tax, "policy_log": policy,
            "preregistration": pre, "validation": json.loads(val_path.read_text()) if val_path.exists() else None,
            "corpus": meta, **extra}
    (ROOT / "demo" / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # ---- docs/RESULTS.md
    out = ["# Results (generated from the research record)\n",
           f"Record entries: {len(rec)} · hash chain intact: **{chain_ok}** · frozen taxonomies: {len(tax)} · experiment runs: {len(results)}\n"]
    tour = [r for r in results if r["experiment"] == "tournament"]
    if tour:
        out.append("## Taxonomy tournament\n\n| record | taxonomy | lang | instrument | testable units | accuracy | null mean | chance-corrected | 95% CI (accuracy) | p (perm.) |\n|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(tour, key=lambda x: (x["result"]["lang"], x["result"]["instrument"], -x["result"]["chance_corrected"])):
            x = r["result"]
            out.append(f"| {r['record_id']} | {x.get('taxonomy_id')} | {x['lang']} | {x['instrument']} | {x['n_testable']}/{x['n_units']} | {x['accuracy']:.3f} | {x['null_mean']:.3f} | "
                       f"{x['chance_corrected']:.3f} | {x['ci95'][0]:.2f}-{x['ci95'][1]:.2f} | {x['p_perm']:.4f} |")
    for r in results:
        x = r["result"]
        if r["experiment"] == "defectors":
            out.append(f"\n## Instrument validation (H-C2), record {r['record_id']}\n\nInstrument `{x['instrument']}`: mean within-book percentile of the pre-registered Daoist-leaning chapters = "
                       f"**{x['mean_target_percentile']:.1f}** (permutation p = {x['p_perm']:.4f}, n = {x['n_targets']}).\n")
            for b, d in x["detail"].items():
                out.append(f"- {b}: {d['target_percentiles']} of {d['n_chapters']} chapters; top 5 by Daoist affinity: {', '.join(d['top5'])}")
        if r["experiment"] == "tomb_test":
            out.append(f"\n## Tomb test (H-C3), record {r['record_id']}\n\nInstrument `{x['instrument']}`, taxonomy `{x.get('taxonomy_id')}`: label shares of the sealed manuscript's {x['n_chunks']} chunks = {x['label_shares']}; "
                       f"dominant share {x['dominant_share']:.2f}; mean margin at the {x['margin_percentile_vs_transmitted']:.0f}th percentile of transmitted books.\n")
        if r["experiment"] == "hindsight_gap":
            out.append(f"\n## Hindsight gap (H-W2), record {r['record_id']}\n\nG = **{x['G']:.3f}** (95% CI {x['ci95'][0]:.3f} to {x['ci95'][1]:.3f}); modern-minus-1930 advantage on the retrospective taxonomy "
                       f"{x['retro_advantage_of_modern']:.3f}, on the contemporary taxonomy {x['contemporary_advantage_of_modern']:.3f}.\n")
        if r["experiment"] == "probe_score":
            out.append(f"\n## Recognition probe, record {r['record_id']}\n\n" + "\n".join(
                f"- {a}: recognised the source book of {v['correct']}/{v['n']} masked passages ({v['recognition_rate']:.0%})" for a, v in x["readers"].items()))
    (ROOT / "docs" / "RESULTS.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"record={len(rec)} chain_ok={chain_ok} results={len(results)} taxonomies={len(tax)} policy_events={len(policy)}")


if __name__ == "__main__":
    main()
