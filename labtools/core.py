"""Shared implementation behind the lab's Omnigent tools.

Tools are thin wrappers (one file per tool in each agent bundle) that call into
this module with a fixed ``actor`` name, so every entry in the research record
is attributed by the orchestration layer, not self-reported by a model.
"""

from __future__ import annotations

import datetime as _dt
import fcntl
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "records" / "research_record.jsonl"
PREREG_PATH = ROOT / "records" / "preregistration.json"
TAX_DIR = ROOT / "taxonomies"
RESULTS = ROOT / "out" / "results"
LAB_PYTHON = os.environ.get("LAB_PYTHON", str(ROOT / ".venv" / "bin" / "python"))
RECORD_TYPES = {"objective", "preregistration", "evidence", "taxonomy_frozen", "critique", "candidate_experiments",
                "decision", "approval_request", "approval", "experiment", "result", "audit", "probe",
                "conclusion", "next_experiment", "note"}


def _prereg() -> dict:
    return json.loads(PREREG_PATH.read_text(encoding="utf-8"))


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_record() -> list[dict]:
    if not RECORD.exists():
        return []
    return [json.loads(l) for l in RECORD.read_text(encoding="utf-8").splitlines() if l.strip()]


def record_append(actor: str, type: str, payload, links=None, hypothesis_origin: str | None = None,
                  credits: int = 0) -> dict:
    """Append one hash-chained entry to the shared research record."""
    if type not in RECORD_TYPES:
        raise ValueError(f"type must be one of {sorted(RECORD_TYPES)}")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"text": payload}
    if isinstance(links, str):
        links = [x.strip() for x in re.split(r"[,\s]+", links) if x.strip()]
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORD, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        lines = [l for l in f.read().splitlines() if l.strip()]
        prev = json.loads(lines[-1])["sha256"] if lines else "GENESIS"
        entry = {"id": f"r{len(lines) + 1:04d}", "ts": _now(), "actor": actor, "type": type, "payload": payload,
                 "links": links or [], "hypothesis_origin": hypothesis_origin, "credits": credits, "prev": prev}
        entry["sha256"] = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)
    return {"id": entry["id"], "ts": entry["ts"], "sha256": entry["sha256"][:16]}


def record_read(last_n: int = 20, type: str = "", actor: str = "") -> list[dict]:
    """Recent record entries. Long payloads are shortened so a reader's context is not flooded;
    narrow the query (type / actor / smaller last_n) to see an entry in full."""
    rows = _read_record()
    if type:
        rows = [r for r in rows if r["type"] == type]
    if actor:
        rows = [r for r in rows if r["actor"] == actor]
    rows = rows[-max(1, min(int(last_n), 60)):]
    cap = 6000 if len(rows) <= 6 else (2500 if len(rows) <= 15 else 900)
    out, total = [], 0
    for r in reversed(rows):
        s = json.dumps(r["payload"], ensure_ascii=False)
        item = {"id": r["id"], "ts": r["ts"], "actor": r["actor"], "type": r["type"], "links": r["links"],
                "payload": r["payload"] if len(s) <= cap else {"shortened": s[:cap], "note": "shortened; query this type/actor with a smaller last_n for the full entry"}}
        total += min(len(s), cap)
        if total > 60000:
            break
        out.append(item)
    return list(reversed(out))


def credits_status() -> dict:
    total = _prereg()["credits_total"]
    used = sum(int(r.get("credits", 0)) for r in _read_record() if r["type"] == "experiment")
    return {"credits_total": total, "credits_used": used, "credits_left": total - used}


# ----------------------------------------------------------------- corpus
def corpus_info(lang: str) -> dict:
    """Units available for labelling (no labels, no results)."""
    meta = json.loads((ROOT / "corpus" / lang / "metadata.json").read_text(encoding="utf-8"))
    pre = _prereg()
    if lang == "zh":
        units = {k: {"title": v["title"], "n_chunks": v["n_chunks"], "n_chars": v["n_chars"],
                     "sealed_do_not_label": k in pre["sealed_units_never_labeled"]} for k, v in meta.items()}
        return {"lang": "zh", "unit": "book", "units": units,
                "note": "Sealed units are excavated manuscripts held out for the tomb test. Never label them."}
    authors: dict[str, dict] = {}
    for v in meta.values():
        a = authors.setdefault(v["author"], {"works": []})
        a["works"].append(v["title"])
    return {"lang": "en", "unit": "author", "units": authors,
            "note": "All works are English texts published before 1931 (Project Gutenberg)."}


# -------------------------------------------------------------- taxonomies
def submit_taxonomy(actor: str, taxonomy_json: str) -> dict:
    """Validate, freeze and hash a taxonomy. Frozen taxonomies cannot be overwritten."""
    try:
        spec = json.loads(taxonomy_json)
    except json.JSONDecodeError as exc:
        return {"error": f"taxonomy_json is not valid JSON: {exc}"}
    for k in ("taxonomy_id", "lang", "title", "source_claim", "labels"):
        if k not in spec:
            return {"error": f"missing field {k!r}"}
    tid = spec["taxonomy_id"]
    if not re.fullmatch(r"[A-Za-z0-9_]{3,40}", tid):
        return {"error": "taxonomy_id must be 3-40 chars of letters, digits or underscore"}
    if spec["lang"] not in ("zh", "en"):
        return {"error": "lang must be 'zh' or 'en'"}
    path = TAX_DIR / f"{tid}.json"
    if path.exists():
        return {"error": f"taxonomy {tid} is already frozen; frozen taxonomies cannot be changed (pre-registration rule)"}
    info = corpus_info(spec["lang"])
    units = info["units"]
    sealed = set(_prereg()["sealed_units_never_labeled"])
    problems, classes = [], {}
    for unit, v in spec["labels"].items():
        if unit not in units:
            problems.append(f"unknown unit {unit!r}")
            continue
        if not isinstance(v, dict) or "label" not in v:
            problems.append(f"{unit}: entry must be an object with 'label', 'confidence', 'citation'")
            continue
        if unit in sealed and v.get("label"):
            problems.append(f"{unit}: sealed unit must not be labelled")
        if v.get("label"):
            cit = str(v.get("citation", ""))
            if not (cit.startswith("http") or cit == "uncertain"):
                problems.append(f"{unit}: citation must be a URL or the word 'uncertain'")
            if v.get("confidence") not in ("high", "medium", "contested"):
                problems.append(f"{unit}: confidence must be high | medium | contested")
            classes.setdefault(v["label"], []).append(unit)
    if sum(len(v) >= 2 for v in classes.values()) < 2:
        problems.append("need at least two classes with two or more units each, otherwise nothing is testable")
    if problems:
        return {"error": "validation failed", "problems": problems[:30]}
    spec["submitted_by"] = actor
    spec["hypothesis_origin"] = "agent"
    spec["frozen_at"] = _now()
    body = json.dumps(spec, ensure_ascii=False, indent=1, sort_keys=True)
    sha = hashlib.sha256(body.encode()).hexdigest()
    TAX_DIR.mkdir(exist_ok=True)
    path.write_text(body, encoding="utf-8")
    rec = record_append(actor, "taxonomy_frozen", {"taxonomy_id": tid, "lang": spec["lang"], "title": spec["title"],
                                                   "source_claim": spec["source_claim"], "sha256": sha,
                                                   "classes": {k: len(v) for k, v in classes.items()},
                                                   "n_contested": sum(1 for v in spec["labels"].values() if v.get("confidence") == "contested"),
                                                   "n_uncertain_citations": sum(1 for v in spec["labels"].values() if v.get("citation") == "uncertain")},
                        hypothesis_origin="agent")
    return {"frozen": tid, "sha256": sha, "record_id": rec["id"], "classes": {k: len(v) for k, v in classes.items()},
            "unlabelled_units": sorted(set(units) - set(k for k, v in spec["labels"].items() if v.get("label")))}


def list_taxonomies() -> list[dict]:
    out = []
    for p in sorted(TAX_DIR.glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        out.append({"taxonomy_id": s["taxonomy_id"], "lang": s["lang"], "title": s["title"], "submitted_by": s.get("submitted_by"),
                    "classes": sorted({v["label"] for v in s["labels"].values() if v.get("label")})})
    return out


def read_taxonomy(taxonomy_id: str) -> dict:
    p = TAX_DIR / f"{taxonomy_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"error": f"no frozen taxonomy {taxonomy_id}"}


# ------------------------------------------------------------- experiments
EXPERIMENTS = {
    "tournament": "Leave-one-unit-out test of one frozen taxonomy. params: taxonomy_id; instrument (zh: lex | lex_tr | qwen ; en: lex | qwen | talkie); optional layer (mid|late|last), masked (bool), exclude_units (list), drop_contested (bool), strip_lacunae (bool: remove the editorial lacuna marks that only occur in excavated manuscripts; applies to lex and lex_tr).",
    "defectors": "Instrument validation H-C2 (pre-registered Daoist-leaning chapters). params: taxonomy_id (must contain classes Daoist and Legalist); instrument (lex | lex_tr | qwen).",
    "tomb_test": "H-C3: where does the sealed Mawangdui manuscript fall? params: taxonomy_id; instrument (lex | lex_tr | qwen); optional strip_lacunae (bool, control for lacuna marks as a surface cue).",
    "hindsight_gap": "H-W2: G = modern-minus-1930 advantage on the retrospective taxonomy minus the same on the contemporary one. It computes its four supporting leave-one-author-out scores itself (retro and contemporary taxonomy on talkie and on qwen) and returns G with a bootstrap interval; separate tournament runs are needed only if you want permutation p-values and intervals for a single taxonomy-instrument pair. params: retro_taxonomy_id, contemporary_taxonomy_id; optional layer.",
    "corpus_map": "Descriptive 2-D map of unit centroids, no labels. params: lang, instrument. Free.",
    "probe_score": "Score the recognition probe (how often blind readers named the source book). Optional params: exclude_passages (list of passage ids to leave out). Free.",
}


def list_experiments() -> dict:
    pre = _prereg()
    return {"experiments": EXPERIMENTS, "costs": pre["experiment_costs"], **credits_status(),
            "preregistered_hypotheses": {k: v["claim"] for k, v in pre["hypotheses"].items()}}


def run_experiment(actor: str, experiment: str, params_json: str = "{}") -> dict:
    """Run one registered experiment; refuses unfrozen taxonomies and overspending."""
    pre = _prereg()
    if experiment not in EXPERIMENTS:
        return {"error": f"unknown experiment; choose from {sorted(EXPERIMENTS)}"}
    try:
        params = json.loads(params_json or "{}")
    except json.JSONDecodeError as exc:
        return {"error": f"params_json is not valid JSON: {exc}"}
    if not any(r["type"] == "preregistration" for r in _read_record()):
        return {"error": "no preregistration entry in the research record; experiments are blocked until a human registers the hypotheses"}
    for key in ("taxonomy_id", "retro_taxonomy_id", "contemporary_taxonomy_id"):
        if key in params and not (TAX_DIR / f"{params[key]}.json").exists():
            return {"error": f"{key}={params[key]!r} is not a frozen taxonomy; submit it with submit_taxonomy first"}
    cost = int(pre["experiment_costs"].get(experiment, 1))
    cs = credits_status()
    if cost > cs["credits_left"]:
        return {"error": "experiment budget exhausted", **cs}
    proc = subprocess.run([LAB_PYTHON, str(ROOT / "analysis" / "cli.py"), experiment, json.dumps(params, ensure_ascii=False)],
                          capture_output=True, text=True, timeout=900, cwd=str(ROOT))
    if proc.returncode != 0:
        return {"error": "experiment failed", "stderr": proc.stderr[-1500:]}
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    exp = record_append(actor, "experiment", {"experiment": experiment, "params": params}, credits=cost)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{exp['id']}_{experiment}.json").write_text(json.dumps({"experiment": experiment, "params": params, "result": result},
                                                                       ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {k: v for k, v in result.items() if k not in ("transmitted_reference", "per_author_retro_diff", "per_author_contemporary_diff")}
    res = record_append(actor, "result", {"experiment": experiment, "params": params, "summary": summary}, links=[exp["id"]])
    if experiment == "defectors":
        ok = result["mean_target_percentile"] >= 80 and result["p_perm"] < 0.05
        vpath = ROOT / "records" / "validation.json"
        prev = json.loads(vpath.read_text()) if vpath.exists() else {"runs": []}
        prev["runs"].append({"record_id": res["id"], "instrument": params.get("instrument", "lex"), "pass": bool(ok),
                             "mean_target_percentile": result["mean_target_percentile"], "p_perm": result["p_perm"]})
        prev["status"] = "PASS" if any(r["pass"] for r in prev["runs"]) else "FAIL"
        vpath.write_text(json.dumps(prev, indent=1))
        (ROOT / "records" / "VALIDATION_STATUS").write_text(prev["status"])
        summary["instrument_validation"] = prev["status"]
    return {"experiment_record": exp["id"], "result_record": res["id"], "credits": credits_status(), "result": summary}


# ---------------------------------------------------------- blind probing
def _probe_batches() -> list[list[dict]]:
    import random

    rows = [json.loads(l) for l in open(ROOT / "corpus" / "zh" / "chunks.jsonl", encoding="utf-8")]
    rng = random.Random(_prereg()["seed"])
    by_book: dict[str, list[dict]] = {}
    for r in rows:
        by_book.setdefault(r["book"], []).append(r)
    picked = []
    for b in sorted(by_book):
        picked += rng.sample(by_book[b], min(3, len(by_book[b])))
    rng.shuffle(picked)
    return [picked[i: i + 8] for i in range(0, len(picked), 8)]


def get_blind_batch(batch_id: int) -> dict:
    batches = _probe_batches()
    if not 0 <= int(batch_id) < len(batches):
        return {"error": f"batch_id must be 0..{len(batches) - 1}"}
    return {"batch_id": int(batch_id), "n_batches": len(batches),
            "passages": [{"id": r["id"], "text": r["text"][:700]} for r in batches[int(batch_id)]],
            "instruction": "Names of people and schools are masked with 〇. For each passage guess which early Chinese book it comes from."}


def submit_probe(actor: str, batch_id: int, guesses_json: str) -> dict:
    try:
        guesses = json.loads(guesses_json)
    except json.JSONDecodeError as exc:
        return {"error": f"guesses_json is not valid JSON: {exc}"}
    ids = {r["id"] for r in _probe_batches()[int(batch_id)]}
    guesses = [g for g in guesses if isinstance(g, dict) and g.get("id") in ids]
    if not guesses:
        return {"error": "no guesses matched the passage ids of this batch"}
    d = ROOT / "out" / "probe"
    d.mkdir(parents=True, exist_ok=True)
    if (d / f"{actor}_batch{int(batch_id)}.json").exists():
        return {"error": f"batch {int(batch_id)} was already submitted by {actor}; the first submission is final"}
    (d / f"{actor}_batch{int(batch_id)}.json").write_text(json.dumps({"actor": actor, "batch_id": int(batch_id), "guesses": guesses},
                                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    rec = record_append(actor, "probe", {"batch_id": int(batch_id), "n_guesses": len(guesses)})
    return {"stored": len(guesses), "record_id": rec["id"]}


# ------------------------------------------------------------- literature
def openalex_search(query: str, per_page: int = 6) -> dict:
    import requests

    r = requests.get("https://api.openalex.org/works", params={"search": query, "per-page": min(int(per_page), 10),
                                                               "mailto": "six-schools-lab@example.org"}, timeout=30)
    if r.status_code != 200:
        return {"error": f"OpenAlex HTTP {r.status_code}"}
    out = []
    for w in r.json().get("results", []):
        out.append({"title": w.get("title"), "year": w.get("publication_year"),
                    "authors": [a["author"]["display_name"] for a in w.get("authorships", [])[:4]],
                    "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                    "cited_by": w.get("cited_by_count"), "url": w.get("doi") or w.get("id")})
    return {"query": query, "results": out}


def wikipedia_lookup(title: str, lang: str = "en", max_chars: int = 2500) -> dict:
    import requests

    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php",
                     params={"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "format": "json",
                             "titles": title}, headers={"User-Agent": "six-schools-lab/0.1"}, timeout=30)
    if r.status_code != 200:
        return {"error": f"Wikipedia HTTP {r.status_code}"}
    pages = r.json().get("query", {}).get("pages", {})
    for p in pages.values():
        if "extract" in p:
            return {"title": p["title"], "url": f"https://{lang}.wikipedia.org/wiki/{p['title'].replace(' ', '_')}",
                    "extract": p["extract"][: int(max_chars)]}
    return {"error": f"no Wikipedia page for {title!r}"}


def check_citation(url: str) -> dict:
    import requests

    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0 six-schools-lab citation check"}, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "ok": False, "error": type(exc).__name__}
    m = re.search(r"<title[^>]*>(.*?)</title>", r.text[:20000], flags=re.S | re.I)
    return {"url": url, "ok": r.status_code == 200, "status": r.status_code, "final_url": r.url,
            "title": re.sub(r"\s+", " ", m.group(1)).strip()[:160] if m else None}


# ------------------------------------------------------------ publication
def request_publication(actor: str, conclusion_json: str) -> dict:
    """Publish the lab's conclusion. Gated by policy: instrument validation + human approval."""
    try:
        c = json.loads(conclusion_json)
    except json.JSONDecodeError:
        c = {"text": conclusion_json}
    rec = record_append(actor, "conclusion", c)
    (ROOT / "out" / "conclusion.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"published": True, "record_id": rec["id"]}
