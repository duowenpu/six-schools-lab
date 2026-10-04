#!/usr/bin/env python3
"""Measured throughput of the lab, computed only from timestamps in the research record.

Optional human baseline: out/human_baseline.json, e.g.
{"task": "formalize one taxonomy: label 23 books with one citation each", "minutes": 42, "who": "team member", "notes": "..."}
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def t(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    rec = [json.loads(l) for l in (ROOT / "records" / "research_record.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    agent = [r for r in rec if r["actor"] not in ("human", "operator")]
    if not agent:
        raise SystemExit("no agent entries yet")
    start, end = t(agent[0]["ts"]), t(agent[-1]["ts"])
    # downtime: from the last agent entry before an operator note to the first agent entry after it
    down = dt.timedelta()
    for i, r in enumerate(rec):
        # only operator notes that mark a real outage or restart count as downtime
        if r["actor"] == "operator" and any(k in str(r["payload"].get("event", "")) for k in ("interruption", "restart")):
            before = [x for x in rec[:i] if x["actor"] not in ("human", "operator")]
            after = [x for x in rec[i + 1:] if x["actor"] not in ("human", "operator")]
            if before and after:
                down += t(after[0]["ts"]) - t(before[-1]["ts"])
    gross = (end - start).total_seconds() / 3600
    net = max(1e-9, gross - down.total_seconds() / 3600)
    frozen = [r for r in rec if r["type"] == "taxonomy_frozen"]
    exps = [r for r in rec if r["type"] == "experiment"]
    tests = [r for r in exps if r["payload"]["experiment"] in ("tournament", "defectors", "tomb_test", "hindsight_gap")]
    lat = []
    for i, r in enumerate(rec):
        if r["type"] == "critique":
            nxt = next((x for x in rec[i + 1:] if x["type"] == "result"), None)
            if nxt:
                lat.append((t(nxt["ts"]) - t(r["ts"])).total_seconds() / 60)
    out = {
        "source": "timestamps of records/research_record.jsonl",
        "wall_clock_hours_gross": round(gross, 2), "infrastructure_downtime_hours": round(down.total_seconds() / 3600, 2),
        "wall_clock_hours_net": round(net, 2),
        "rival_taxonomies_formalized_with_citations": len(frozen),
        "controlled_tests_run": len(tests),
        "taxonomies_per_hour_net": round(len(frozen) / net, 2),
        "controlled_tests_per_hour_net": round(len(tests) / net, 2),
        "minutes_from_critique_to_next_result": [round(x, 1) for x in lat],
        "caveats": ["one lab run, one corpus", "agent labels are checked for citation resolution, not for scholarly quality",
                    "the human baseline is a single timed trial by one person"],
    }
    hb = ROOT / "out" / "human_baseline.json"
    ad = ROOT / "out" / "advocate_durations.json"
    if ad.exists():
        a = json.loads(ad.read_text(encoding="utf-8"))
        out["agent_minutes_per_taxonomy"] = {k: a[k] for k in ("median_minutes", "mean_minutes", "min_minutes", "max_minutes", "n", "source", "note")}
    # one batch of taxonomies formalized in parallel: the four English taxonomies of PHASE 2
    en = [r for r in frozen if r["payload"].get("lang") == "en"]
    if en and ad.exists():
        per = json.loads(ad.read_text(encoding="utf-8"))["per_taxonomy"]
        starts = [t(r["ts"]) - dt.timedelta(minutes=per[r["payload"]["taxonomy_id"]]["minutes"]) for r in en if r["payload"]["taxonomy_id"] in per]
        if starts:
            wall = (max(t(r["ts"]) for r in en) - min(starts)).total_seconds() / 60
            out["parallel_batch"] = {"taxonomies": len(en), "wall_clock_minutes": round(wall, 1)}
    if hb.exists():
        h = json.loads(hb.read_text(encoding="utf-8"))
        out["human_baseline"] = h
        if "agent_minutes_per_taxonomy" in out:
            out["speedup_single_taxonomy"] = round(h["minutes"] / out["agent_minutes_per_taxonomy"]["median_minutes"], 2)
        if "parallel_batch" in out:
            pb = out["parallel_batch"]
            pb["one_person_sequential_minutes_extrapolated"] = round(h["minutes"] * pb["taxonomies"], 1)
            out["speedup_parallel_batch"] = round(h["minutes"] * pb["taxonomies"] / pb["wall_clock_minutes"], 2)
        out["caveats"].append("the sequential human time for a batch is the single timed trial multiplied by the number of taxonomies")
    (ROOT / "out" / "acceleration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
