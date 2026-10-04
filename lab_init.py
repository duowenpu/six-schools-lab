#!/usr/bin/env python3
"""Human step before the first Omnigent session: write the objective and the
pre-registration into the hash-chained research record. Refuses to run twice."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from labtools import core  # noqa: E402

if core.RECORD.exists() and core.RECORD.read_text().strip():
    sys.exit("research record already initialised")
pre = json.loads(core.PREREG_PATH.read_text(encoding="utf-8"))
sha = hashlib.sha256(core.PREREG_PATH.read_bytes()).hexdigest()
print(core.record_append("human", "objective", {"objective": pre["objective"]}, hypothesis_origin="human"))
print(core.record_append("human", "preregistration", {
    "file": "records/preregistration.json", "sha256": sha, "hypotheses": pre["hypotheses"],
    "decision_rules_after_first_tournament": pre["decision_rules_after_first_tournament"],
    "credits_total": pre["credits_total"], "experiment_costs": pre["experiment_costs"],
    "disclosure": "Lab tooling (corpus builders, instruments, statistics, tools, policies) was written before this run. "
                  "A pipeline smoke test with a throwaway labelling was run during tool development; it is not a reported result. "
                  "All taxonomies, experiment choices, runs, critiques and conclusions below are produced by the Omnigent agents."},
    links=["r0001"], hypothesis_origin="human"))
