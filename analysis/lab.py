#!/usr/bin/env python3
"""Core statistics for the Six Schools Lab.

Everything here is deterministic given (corpus, instrument, taxonomy, seed).

Instruments (how a chunk becomes a vector):
  lex        TF-IDF of character bigrams (zh) / word 1-2 grams (en), names masked
  lex_tr     same, on the modern-Chinese translation (style control, zh only)
  qwen       mean-pooled hidden state of the modern reader model
  talkie     mean-pooled hidden state of the sealed 1930 reader model (en only)

Tournament: leave-one-unit-out (unit = book for zh, author for en). A taxonomy
scores well if chunks of a held-out unit fall nearest to the centroid of the
*other* units that share its label. Null: unit-level label permutation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UNIT_KEY = {"zh": "book", "en": "author"}


# ----------------------------------------------------------------- loading
@lru_cache(maxsize=None)
def chunks(lang: str) -> list[dict]:
    return [json.loads(l) for l in open(ROOT / "corpus" / lang / "chunks.jsonl", encoding="utf-8")]


def units_of(lang: str) -> np.ndarray:
    return np.array([c[UNIT_KEY[lang]] for c in chunks(lang)])


def _l2(X: np.ndarray) -> np.ndarray:
    return X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)


@lru_cache(maxsize=None)
def vectors(lang: str, instrument: str, layer: str = "mid", masked: bool = True) -> np.ndarray:
    """Return an (n_chunks, d) matrix, mean-centred and L2-normalised."""
    cs = chunks(lang)
    if instrument in ("lex", "lex_tr"):
        from sklearn.feature_extraction.text import TfidfVectorizer

        if instrument == "lex_tr":
            texts = [c["translation"] for c in cs]
        else:
            texts = [c["text"] if masked else c["text_raw"] for c in cs]
        if lang == "zh":
            vec = TfidfVectorizer(analyzer="char", ngram_range=(2, 2), max_features=3000, sublinear_tf=True, min_df=3)
        else:
            vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), max_features=5000, sublinear_tf=True,
                                  min_df=5, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b", lowercase=True)
        X = vec.fit_transform(texts).toarray().astype(np.float32)
    else:
        z = np.load(ROOT / "out" / f"{lang}_{instrument}.npz", allow_pickle=False)
        ids = [str(i) for i in z["ids"]]
        assert ids == [c["id"] for c in cs], "embedding ids do not match corpus order"
        layers = sorted(int(k[5:]) for k in z.files if k.startswith("emb_L"))
        pick = {"mid": layers[0], "late": layers[len(layers) // 2], "last": layers[-1]}[layer]
        X = z[f"emb_L{pick}"].astype(np.float32)
    X = X - X.mean(axis=0, keepdims=True)
    return _l2(X)


# -------------------------------------------------------------- tournament
def _prep(X: np.ndarray, unit: np.ndarray, unit_names: list[str]):
    G = _l2(np.stack([X[unit == u].mean(axis=0) for u in unit_names]))
    S = X @ G.T            # chunk x unit-centroid similarity
    GG = G @ G.T           # unit x unit
    owner = np.array([unit_names.index(u) for u in unit])
    return S, GG, owner


def _score(S, GG, owner, y: np.ndarray) -> np.ndarray:
    """Per-unit leave-one-out accuracy for integer labels y (-1 = unlabeled). NaN if untestable."""
    n_units = len(y)
    labs = [l for l in np.unique(y) if l >= 0]
    out = np.full(n_units, np.nan)
    for g in range(n_units):
        if y[g] < 0:
            continue
        rows = owner == g
        if not rows.any():
            continue
        sims, valid = [], []
        for l in labs:
            members = np.where((y == l) & (np.arange(n_units) != g))[0]
            if len(members) == 0:
                continue
            num = S[rows][:, members].mean(axis=1)
            den = np.sqrt(GG[np.ix_(members, members)].mean())
            sims.append(num / max(den, 1e-12))
            valid.append(l)
        if y[g] not in valid or len(valid) < 2:
            continue  # singleton label: cannot be tested out of sample
        pred = np.array(valid)[np.argmax(np.stack(sims, axis=1), axis=1)]
        out[g] = float((pred == y[g]).mean())
    return out


def tournament(lang: str, instrument: str, labels: dict[str, str | None], *, layer: str = "mid",
               masked: bool = True, n_perm: int = 2000, seed: int = 20261003,
               restrict_units: list[str] | None = None) -> dict:
    X = vectors(lang, instrument, layer, masked)
    unit = units_of(lang)
    names = sorted(set(unit))
    if restrict_units is not None:
        names = [n for n in names if n in set(restrict_units)]
    keep = np.isin(unit, names)
    S, GG, owner = _prep(X[keep], unit[keep], names)
    classes = sorted({v for k, v in labels.items() if v and k in names})
    y = np.array([classes.index(labels[n]) if labels.get(n) else -1 for n in names])
    per_unit = _score(S, GG, owner, y)
    testable = ~np.isnan(per_unit)
    obs = float(np.nanmean(per_unit)) if testable.any() else float("nan")
    rng = np.random.default_rng(seed)
    labeled = np.where(y >= 0)[0]
    null = np.empty(n_perm)
    for i in range(n_perm):
        yp = y.copy()
        yp[labeled] = rng.permutation(y[labeled])
        s = _score(S, GG, owner, yp)
        null[i] = np.nanmean(s) if (~np.isnan(s)).any() else np.nan
    null = null[~np.isnan(null)]
    p = float((1 + (null >= obs).sum()) / (len(null) + 1))
    kappa = float((obs - null.mean()) / max(1e-9, 1 - null.mean()))
    vals = per_unit[testable]
    boot = np.array([rng.choice(vals, len(vals)).mean() for _ in range(2000)]) if len(vals) else np.array([np.nan])
    return {
        "lang": lang, "instrument": instrument, "layer": layer, "masked": masked,
        "n_units": len(names), "n_labeled": int((y >= 0).sum()), "n_testable": int(testable.sum()),
        "n_classes": len(classes), "accuracy": obs, "null_mean": float(null.mean()), "null_sd": float(null.std()),
        "z": float((obs - null.mean()) / max(null.std(), 1e-9)), "p_perm": p, "chance_corrected": kappa,
        "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
        "per_unit": {n: (None if np.isnan(v) else round(float(v), 4)) for n, v in zip(names, per_unit)},
        "untestable": [n for n, v, l in zip(names, per_unit, y) if l >= 0 and np.isnan(v)],
    }


# ------------------------------------------------- label centroids (shared)
def _label_centroids(X, unit, labels, exclude_units=()):
    names = [n for n in sorted(set(unit)) if labels.get(n) and n not in exclude_units]
    cents = {}
    for lab in sorted({labels[n] for n in names}):
        members = [n for n in names if labels[n] == lab]
        G = _l2(np.stack([X[unit == m].mean(axis=0) for m in members]))
        cents[lab] = _l2(G.mean(axis=0, keepdims=True))[0]
    return cents


# -------------------------------------------- C2: known-defector validation
def defectors(instrument: str, labels: dict[str, str], targets: dict[str, list[str]], *,
              pos: str = "Daoist", neg: str = "Legalist", n_perm: int = 10000, seed: int = 20261003, layer: str = "mid") -> dict:
    """Do chapters that scholars call Daoist-leaning rank high on Daoist affinity within their own book?"""
    X, unit, cs = vectors("zh", instrument, layer), units_of("zh"), chunks("zh")
    rng = np.random.default_rng(seed)
    pct_all, detail, null_sets = [], {}, []
    for book, chaps in targets.items():
        cents = _label_centroids(X, unit, labels, exclude_units=(book,))
        if pos not in cents or neg not in cents:
            continue
        rows = np.where(unit == book)[0]
        aff = X[rows] @ cents[pos] - X[rows] @ cents[neg]
        by_ch: dict[str, list[float]] = {}
        for r, a in zip(rows, aff):
            for ch in cs[r]["chapters"]:
                by_ch.setdefault(ch, []).append(float(a))
        names = sorted(by_ch)
        score = np.array([np.mean(by_ch[n]) for n in names])
        rank_pct = (score.argsort().argsort() + 0.5) / len(score) * 100
        found = [c for c in chaps if c in names]
        idx = [names.index(c) for c in found]
        pct_all += list(rank_pct[idx])
        detail[book] = {"n_chapters": len(names), "targets_found": found,
                        "target_percentiles": {c: round(float(rank_pct[i]), 1) for c, i in zip(found, idx)},
                        "top5": [names[i] for i in np.argsort(-score)[:5]]}
        null_sets.append((rank_pct, len(idx)))
    obs = float(np.mean(pct_all)) if pct_all else float("nan")
    null = np.array([np.mean(np.concatenate([rng.choice(rp, k, replace=False) for rp, k in null_sets if k]))
                     for _ in range(n_perm)]) if pct_all else np.array([np.nan])
    return {"instrument": instrument, "mean_target_percentile": obs, "p_perm": float((1 + (null >= obs).sum()) / (len(null) + 1)),
            "n_targets": len(pct_all), "detail": detail}


# ------------------------------------------------------- C3: the tomb test
def tomb_test(instrument: str, labels: dict[str, str], sealed: str = "Huangdi_Sijing", layer: str = "mid") -> dict:
    """Where does a manuscript sealed before the taxonomy existed fall among transmitted books?"""
    X, unit = vectors("zh", instrument, layer), units_of("zh")
    transmitted = [n for n in sorted(set(unit)) if labels.get(n)]

    def margins(target, exclude):
        cents = _label_centroids(X, unit, labels, exclude_units=exclude)
        labs = sorted(cents)
        sims = X[unit == target] @ np.stack([cents[l] for l in labs]).T
        order = np.sort(sims, axis=1)
        pred = np.array(labs)[sims.argmax(axis=1)]
        return pred, order[:, -1] - order[:, -2], sims.mean(axis=0), labs

    ref = {}
    for b in transmitted:
        pred, m, _, _ = margins(b, (b,))
        vals, counts = np.unique(pred, return_counts=True)
        ref[b] = {"mean_margin": float(m.mean()), "dominant_share": float(counts.max() / counts.sum()),
                  "dominant": str(vals[counts.argmax()]), "label": labels[b]}
    pred, m, mean_sims, labs = margins(sealed, (sealed,))
    vals, counts = np.unique(pred, return_counts=True)
    shares = {str(v): round(float(c / counts.sum()), 3) for v, c in zip(vals, counts)}
    ref_m = np.array([r["mean_margin"] for r in ref.values()])
    ref_d = np.array([r["dominant_share"] for r in ref.values()])
    return {"instrument": instrument, "sealed": sealed, "n_chunks": int((unit == sealed).sum()),
            "label_shares": shares, "dominant_share": float(counts.max() / counts.sum()),
            "mean_similarity_to_label": {l: round(float(s), 4) for l, s in zip(labs, mean_sims)},
            "mean_margin": float(m.mean()),
            "margin_percentile_vs_transmitted": float((ref_m < m.mean()).mean() * 100),
            "dominant_share_percentile_vs_transmitted": float((ref_d < counts.max() / counts.sum()).mean() * 100),
            "transmitted_reference": ref}


# -------------------------------------------------- W2: the hindsight gap
def hindsight_gap(retro: dict[str, str], contemporary: dict[str, str], *, modern: str = "qwen", sealed: str = "talkie",
                  layer: str = "mid", n_boot: int = 4000, seed: int = 20261003) -> dict:
    """G = [S(retro, modern) - S(retro, sealed)] - [S(contemporary, modern) - S(contemporary, sealed)]."""
    res = {(t, i): tournament("en", i, lab, layer=layer, n_perm=200)["per_unit"]
           for t, lab in (("retro", retro), ("contemporary", contemporary)) for i in (modern, sealed)}
    authors = sorted(res[("retro", modern)])

    def diff(t):
        return {a: res[(t, modern)][a] - res[(t, sealed)][a] for a in authors
                if res[(t, modern)][a] is not None and res[(t, sealed)][a] is not None}

    d_r, d_c = diff("retro"), diff("contemporary")
    g = float(np.mean(list(d_r.values())) - np.mean(list(d_c.values())))
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        s = rng.choice(authors, len(authors))
        a = [d_r[x] for x in s if x in d_r]
        b = [d_c[x] for x in s if x in d_c]
        if a and b:
            boots.append(np.mean(a) - np.mean(b))
    return {"G": g, "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "retro_advantage_of_modern": float(np.mean(list(d_r.values()))),
            "contemporary_advantage_of_modern": float(np.mean(list(d_c.values()))),
            "n_authors_retro": len(d_r), "n_authors_contemporary": len(d_c), "layer": layer,
            "per_author_retro_diff": {k: round(v, 4) for k, v in d_r.items()},
            "per_author_contemporary_diff": {k: round(v, 4) for k, v in d_c.items()}}


def load_taxonomy(path: str | Path) -> tuple[dict, dict[str, str | None]]:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    return spec, {k: (v.get("label") if isinstance(v, dict) else v) for k, v in spec["labels"].items()}
