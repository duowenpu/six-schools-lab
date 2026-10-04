#!/usr/bin/env python3
"""Print the research record compactly (one line per entry)."""
import json
import sys
from pathlib import Path

rec = Path(__file__).resolve().parents[1] / "records" / "research_record.jsonl"
start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
for i, line in enumerate(rec.read_text(encoding="utf-8").splitlines()):
    if i < start or not line.strip():
        continue
    r = json.loads(line)
    print(r["id"], r["ts"][11:19], f"{r['actor']:12s}", f"{r['type']:22s}", json.dumps(r["payload"], ensure_ascii=False)[:170])
