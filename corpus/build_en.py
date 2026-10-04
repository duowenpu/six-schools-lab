#!/usr/bin/env python3
"""Build the English (pre-1931) philosophy corpus from Project Gutenberg.

Output: corpus/en/chunks.jsonl (one row per 600-word chunk, names masked),
        corpus/en/metadata.json, corpus/en/provenance.json, corpus/en/mask_list.txt
No school / nationality / era labels are assigned here: those are submitted
later by advocate agents with citations (see taxonomies/).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT.parent / "data_raw" / "gutenberg"
OUT = ROOT / "en"
CHUNK_WORDS = 600
MAX_CHUNKS_PER_BOOK = 60
SEED = 20261003

# author -> [(gutenberg_id, short title)]
BOOKS = {
    "Russell": [(5827, "The Problems of Philosophy"), (25447, "Mysticism and Logic"),
                (37090, "Our Knowledge of the External World"), (2529, "The Analysis of Mind")],
    "Moore": [(53430, "Principia Ethica"), (50141, "Philosophical Studies")],
    "Whitehead": [(18835, "The Concept of Nature"), (68611, "Science and the Modern World")],
    "Bergson": [(26163, "Creative Evolution"), (56852, "Time and Free Will")],
    "Nietzsche": [(4363, "Beyond Good and Evil"), (39955, "The Dawn of Day"),
                  (51356, "The Birth of Tragedy"), (38145, "Human, All Too Human")],
    "Schopenhauer": [(38427, "The World as Will and Idea, vol. 1"), (10732, "Studies in Pessimism"),
                     (44929, "The Basis of Morality")],
    "Hegel": [(55108, "The Logic of Hegel"), (39064, "Philosophy of Mind")],
    "Kant": [(4280, "The Critique of Pure Reason"), (52821, "Prolegomena"),
             (5682, "Fundamental Principles of the Metaphysic of Morals")],
    "Kierkegaard": [(60333, "Selections from the Writings of Kierkegaard")],
    "Croce": [(9306, "Aesthetic"), (54137, "Logic as the Science of the Pure Concept"),
              (54938, "The Philosophy of the Practical")],
    "Eucken": [(43719, "Life's Basis and Life's Ideal"), (43405, "Ethics and Modern Thought")],
    "Comte": [(53799, "A General View of Positivism")],
    "Poincare": [(39713, "The Foundations of Science")],
    "Mach": [(39508, "Popular Scientific Lectures")],
    "Bosanquet": [(63598, "The Essentials of Logic"), (63249, "The Philosophical Theory of the State")],
    "Green": [(61889, "Lectures on the Principles of Political Obligation")],
    "Royce": [(33677, "The Sources of Religious Insight")],
    "James": [(5116, "Pragmatism"), (5117, "The Meaning of Truth"), (11984, "A Pluralistic Universe"),
              (32547, "Essays in Radical Empiricism")],
    "Dewey": [(40089, "Reconstruction in Philosophy"), (40794, "Essays in Experimental Logic"),
              (51525, "The Influence of Darwin on Philosophy"), (41386, "Human Nature and Conduct")],
    "Peirce": [(65274, "Chance, Love, and Logic")],
    "Santayana": [(15000, "The Life of Reason"), (77155, "Scepticism and Animal Faith"),
                  (17771, "Winds of Doctrine")],
    "Perry": [(25110, "The Approach to Philosophy"), (22135, "The Moral Economy")],
    "Mill": [(11224, "Utilitarianism"), (27942, "A System of Logic"), (16833, "Auguste Comte and Positivism")],
    "Spencer": [(55046, "First Principles"), (46129, "The Data of Ethics")],
    "Sidgwick": [(46743, "The Methods of Ethics")],
}

# Names masked in every chunk (authors + philosophers they discuss).
MASK = sorted(set(list(BOOKS) + """Plato Aristotle Socrates Kant Hegel Hume Locke Berkeley Descartes Spinoza
Leibniz Leibnitz Fichte Schelling Lotze Bradley Darwin Frege Meinong Husserl Zarathustra Wagner Goethe
Bentham Hamilton Reid Rousseau Voltaire Pascal Epicurus Heraclitus Parmenides Democritus Newton Galileo
Einstein Poincaré Cantor Peano Kantian Hegelian Platonic Aristotelian Cartesian Darwinian Newtonian
Bergsonian Nietzschean Comtean Spencerian Schiller Lange Herbart Wundt Fechner Helmholtz Emerson
Carlyle Coleridge Stirner Feuerbach Marx Engels Strauss Renan Taine Montaigne Bacon Hobbes Butler
Paley Whewell Bain Huxley Tyndall Clifford Pearson Jevons Boole Venn Whitehead Russell""".split()), key=len, reverse=True)
MASK_RE = re.compile(r"\b(" + "|".join(re.escape(m) for m in MASK) + r")(?:'s|s')?\b")

GERMAN = set("der die das und ist nicht ein eine den dem des sich mit auf für von zu daß dass sind wird kann auch".split())


def fetch(gid: int) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f"pg{gid}.txt"
    if not p.exists():
        for url in (f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
                    f"https://www.gutenberg.org/ebooks/{gid}.txt.utf-8"):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "six-schools-lab/0.1 (research)"})
                data = urllib.request.urlopen(req, timeout=60).read()
                if len(data) > 20000:
                    p.write_bytes(data)
                    break
            except Exception as exc:  # noqa: BLE001
                print(f"  fetch failed {url}: {exc}", file=sys.stderr)
            time.sleep(1.0)
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def body_of(text: str) -> str:
    s = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text)
    e = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    return text[s.end() if s else 0: e.start() if e else len(text)]


def good_chunk(words: list[str]) -> bool:
    joined = " ".join(words)
    alpha = sum(c.isalpha() or c.isspace() for c in joined) / max(1, len(joined))
    if alpha < 0.93:
        return False  # tables, indexes, formulae
    low = [w.lower().strip(".,;:!?()\"'") for w in words]
    if sum(w in GERMAN for w in low) / len(low) > 0.08:
        return False  # German half of bilingual editions
    if sum(len(w) <= 2 for w in low) / len(low) > 0.42:
        return False
    return True


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    rows, meta, prov = [], {}, {}
    for author, books in BOOKS.items():
        for gid, title in books:
            raw = fetch(gid)
            if not raw:
                print(f"MISSING {author} {gid} {title}")
                continue
            words = body_of(raw).split()
            # skip front matter (title pages, translator prefaces) and back matter (indexes)
            words = words[int(len(words) * 0.08): int(len(words) * 0.95)]
            chunks = [words[i: i + CHUNK_WORDS] for i in range(0, len(words) - CHUNK_WORDS + 1, CHUNK_WORDS)]
            chunks = [c for c in chunks if good_chunk(c)]
            if len(chunks) > MAX_CHUNKS_PER_BOOK:
                idx = sorted(rng.sample(range(len(chunks)), MAX_CHUNKS_PER_BOOK))
                chunks = [chunks[i] for i in idx]
            book_key = f"pg{gid}"
            prov[book_key] = {"source": "Project Gutenberg", "url": f"https://www.gutenberg.org/ebooks/{gid}",
                              "sha256": hashlib.sha256(raw.encode()).hexdigest(), "n_chunks": len(chunks)}
            meta[book_key] = {"author": author, "title": title, "gutenberg_id": gid}
            for j, c in enumerate(chunks):
                raw_text = " ".join(c)
                rows.append({"id": f"en_{book_key}_{j:03d}", "book": book_key, "author": author,
                             "text": MASK_RE.sub("[NAME]", raw_text), "text_raw": raw_text})
            print(f"{author:13s} pg{gid:<6d} {len(chunks):3d} chunks  {title}")
    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / "blind.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "text": r["text"]}, ensure_ascii=False) + "\n")
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=1))
    (OUT / "mask_list.txt").write_text("\n".join(MASK) + "\n")
    print(f"TOTAL {len(rows)} chunks, {len(meta)} books, {len({m['author'] for m in meta.values()})} authors")


if __name__ == "__main__":
    main()
