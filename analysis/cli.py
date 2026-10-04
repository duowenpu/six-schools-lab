#!/usr/bin/env python3
"""Experiment runner used by the lab tools: `python analysis/cli.py <experiment> '<params json>'`.

Prints one JSON object. Only frozen taxonomies (taxonomies/<id>.json) can be used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PREREG = json.loads((ROOT / "records" / "preregistration.json").read_text(encoding="utf-8"))


def _tax(tid: str):
    spec, labels = lab.load_taxonomy(ROOT / "taxonomies" / f"{tid}.json")
    return spec, labels


def _balanced(lang: str, k: int | None):
    """Optionally cap every unit at k chunks (seeded) to control for unit size."""
    if not k:
        return None
    rng = np.random.default_rng(PREREG["seed"])
    unit = lab.units_of(lang)
    keep = np.zeros(len(unit), dtype=bool)
    for u in sorted(set(unit)):
        idx = np.where(unit == u)[0]
        keep[rng.choice(idx, min(k, len(idx)), replace=False)] = True
    return keep


def run(experiment: str, p: dict) -> dict:
    layer = p.get("layer", "mid")
    if p.get("strip_lacunae"):
        lab.STRIP_LACUNAE = True
    if experiment == "tournament":
        spec, labels = _tax(p["taxonomy_id"])
        lang = spec["lang"]
        excl = set(p.get("exclude_units", []))
        units = [u for u in sorted(set(lab.units_of(lang))) if u not in excl]
        if p.get("drop_contested"):
            labels = {k: (None if spec["labels"][k].get("confidence") == "contested" else v) for k, v in labels.items()}
        r = lab.tournament(lang, p.get("instrument", "lex"), labels, layer=layer, masked=p.get("masked", True),
                           restrict_units=units)
        r["taxonomy_id"] = p["taxonomy_id"]
        return r
    if experiment == "defectors":
        _, labels = _tax(p["taxonomy_id"])
        t = PREREG["defector_targets"]
        return lab.defectors(p.get("instrument", "lex"), labels, t["chapters"], pos=t["positive_label"],
                             neg=t["negative_label"], layer=layer) | {"taxonomy_id": p["taxonomy_id"]}
    if experiment == "tomb_test":
        _, labels = _tax(p["taxonomy_id"])
        return lab.tomb_test(p.get("instrument", "lex"), labels, sealed=PREREG["sealed_text"], layer=layer) | {
            "taxonomy_id": p["taxonomy_id"]}
    if experiment == "hindsight_gap":
        _, retro = _tax(p["retro_taxonomy_id"])
        _, cont = _tax(p["contemporary_taxonomy_id"])
        return lab.hindsight_gap(retro, cont, layer=layer) | {
            "retro_taxonomy_id": p["retro_taxonomy_id"], "contemporary_taxonomy_id": p["contemporary_taxonomy_id"]}
    if experiment == "corpus_map":
        lang, inst = p["lang"], p.get("instrument", "lex")
        X, unit = lab.vectors(lang, inst, layer), lab.units_of(lang)
        names = sorted(set(unit))
        G = np.stack([X[unit == u].mean(axis=0) for u in names])
        G = G - G.mean(axis=0)
        U, S, _ = np.linalg.svd(G, full_matrices=False)
        xy = U[:, :2] * S[:2]
        return {"lang": lang, "instrument": inst, "explained": [float(v) for v in (S[:2] ** 2 / (S ** 2).sum())],
                "points": {n: [round(float(a), 4), round(float(b), 4)] for n, (a, b) in zip(names, xy)}}
    if experiment == "probe_score":
        alias = PREREG["probe_aliases"]
        meta = {c["id"]: c for c in lab.chunks("zh")}
        out = {}
        excluded = set(p.get("exclude_passages", []))
        for f in sorted((ROOT / "out" / "probe").glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            s = out.setdefault(d["actor"], {"n": 0, "correct": 0, "by_book": {}})
            for g in d["guesses"]:
                if g["id"] in excluded:
                    continue
                true = meta[g["id"]]["book"]
                guess = str(g.get("guess_book", ""))
                ok = any(a in guess for a in [true] + alias.get(true, []))
                s["n"] += 1
                s["correct"] += int(ok)
                b = s["by_book"].setdefault(true, [0, 0])
                b[0] += int(ok)
                b[1] += 1
        for s in out.values():
            s["recognition_rate"] = round(s["correct"] / max(1, s["n"]), 3)
        return {"readers": out, "excluded_passages": sorted(excluded)}
    raise SystemExit(f"unknown experiment {experiment}")


if __name__ == "__main__":
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    res = run(sys.argv[1], params)
    if params.get("strip_lacunae") and isinstance(res, dict):
        res["strip_lacunae"] = True
    print(json.dumps(res, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
