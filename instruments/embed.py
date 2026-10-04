#!/usr/bin/env python3
"""Batch embedding instrument (runs inside a GPU container, offline).

Reads JSONL rows {"id": ..., "text": ...}, runs a causal LM once per text and
writes mean-pooled hidden states at several relative depths plus the mean
token negative log-likelihood (how "familiar" the text is to the model).

The same script is used for every reader model (the sealed 1930 model and the
modern comparison model) so that extraction is identical across readers.
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEPTHS = (0.5, 0.75, 1.0)


def find_blocks(model):
    for path in ("blocks", "model.layers", "transformer.h", "model.decoder.layers"):
        obj = model
        try:
            for part in path.split("."):
                obj = getattr(obj, part)
        except AttributeError:
            continue
        if isinstance(obj, torch.nn.ModuleList) and len(obj) > 0:
            return obj
    raise RuntimeError("could not locate transformer blocks")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sanity", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, trust_remote_code=True, dtype=torch.bfloat16,
        device_map={"": "cuda"}, use_safetensors=True,
    )
    model.eval()
    blocks = find_blocks(model)
    n = len(blocks)
    idx = sorted({max(0, min(n - 1, round(d * n) - 1)) for d in DEPTHS})
    print(f"loaded {args.model} in {time.time()-t0:.1f}s; blocks={n}; tap layers={idx}", flush=True)

    grabbed = {}

    def make_hook(i):
        def hook(_m, _inp, out):
            h = out[0] if isinstance(out, (tuple, list)) else out
            grabbed[i] = h.detach()
        return hook

    handles = [blocks[i].register_forward_hook(make_hook(i)) for i in idx]

    if args.sanity:
        for p in ["The President of the United States is",
                  "The most recent great war in Europe was",
                  "The greatest living philosophers are",
                  "The two main schools of philosophy today are"]:
            ids = tok(p, return_tensors="pt").to("cuda")
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=40, do_sample=False)
            print("SANITY>", repr(tok.decode(out[0], skip_special_tokens=True)), flush=True)

    rows = [json.loads(l) for l in open(args.inp, encoding="utf-8") if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    embs = {i: [] for i in idx}
    nll, ntok, ids_out = [], [], []
    t1 = time.time()
    for k, r in enumerate(rows):
        enc = tok(r["text"], return_tensors="pt", truncation=True, max_length=args.max_tokens)
        input_ids = enc["input_ids"].to("cuda")
        with torch.no_grad():
            out = model(input_ids=input_ids)
        logits = out.logits.float()
        if input_ids.shape[1] > 1:
            loss = torch.nn.functional.cross_entropy(logits[0, :-1], input_ids[0, 1:])
            nll.append(float(loss))
        else:
            nll.append(float("nan"))
        ntok.append(int(input_ids.shape[1]))
        for i in idx:
            embs[i].append(grabbed[i][0].float().mean(dim=0).cpu().numpy().astype(np.float32))
        ids_out.append(r["id"])
        if (k + 1) % 50 == 0 or k + 1 == len(rows):
            dt = time.time() - t1
            print(f"{k+1}/{len(rows)} texts, {dt/(k+1):.2f}s/text, {sum(ntok)/dt:.0f} tok/s", flush=True)
    for h in handles:
        h.remove()
    np.savez_compressed(
        args.out, ids=np.array(ids_out), nll=np.array(nll, dtype=np.float32),
        ntok=np.array(ntok), layers=np.array(idx),
        **{f"emb_L{i}": np.stack(embs[i]) for i in idx},
    )
    print(f"wrote {args.out}; total {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
