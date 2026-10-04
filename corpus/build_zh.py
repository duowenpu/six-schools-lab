#!/usr/bin/env python3
"""Build the Chinese (pre-Qin / early Han) corpus from NiuTrans/Classical-Modern (MIT).

Output: corpus/zh/chunks.jsonl  (classical text, names masked, + aligned modern translation)
        corpus/zh/blind.jsonl   (id + masked classical text only; what blind readers see)
        corpus/zh/metadata.json, provenance.json, mask_list.txt
No school / era / region labels are assigned here: advocates submit those with citations.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "data_raw" / "Classical-Modern" / "双语数据"
OUT = ROOT / "zh"
MIN_CHARS, MAX_CHARS = 600, 1200

TRANSMITTED = ("论语 孟子 荀子 礼记 孝经 孔子家语 中庸 墨子 老子 庄子 列子 韩非子 商君书 管子 公孙龙子 "
               "吕氏春秋 淮南子 鬼谷子 孙子兵法 吴子 六韬 司马法 尉缭子").split()
SEALED = "黄帝四经 孙膑兵法".split()  # excavated manuscripts, never edited by Han collators

# English identifiers used everywhere outside the raw text (results, records, taxonomies).
BOOK_EN = {"论语": ("Analects", "Lunyu / Analects"), "孟子": ("Mencius", "Mengzi / Mencius"), "荀子": ("Xunzi", "Xunzi"),
           "礼记": ("Liji", "Liji / Book of Rites"), "孝经": ("Xiaojing", "Xiaojing / Classic of Filial Piety"),
           "孔子家语": ("Kongzi_Jiayu", "Kongzi Jiayu / School Sayings of Confucius"), "中庸": ("Zhongyong", "Zhongyong / Doctrine of the Mean"),
           "墨子": ("Mozi", "Mozi"), "老子": ("Laozi", "Laozi / Daodejing"), "庄子": ("Zhuangzi", "Zhuangzi"), "列子": ("Liezi", "Liezi"),
           "韩非子": ("Han_Feizi", "Han Feizi"), "商君书": ("Shangjunshu", "Shangjunshu / Book of Lord Shang"), "管子": ("Guanzi", "Guanzi"),
           "公孙龙子": ("Gongsun_Longzi", "Gongsun Longzi"), "吕氏春秋": ("Lushi_Chunqiu", "Lüshi Chunqiu"), "淮南子": ("Huainanzi", "Huainanzi"),
           "鬼谷子": ("Guiguzi", "Guiguzi"), "孙子兵法": ("Sunzi_Bingfa", "Sunzi Bingfa / Art of War"), "吴子": ("Wuzi", "Wuzi"),
           "六韬": ("Liutao", "Liutao / Six Secret Teachings"), "司马法": ("Sima_Fa", "Sima Fa"), "尉缭子": ("Wei_Liaozi", "Wei Liaozi"),
           "黄帝四经": ("Huangdi_Sijing", "Mawangdui silk manuscripts ('Huangdi Sijing'), buried 168 BCE"),
           "孙膑兵法": ("Sun_Bin_Bingfa", "Sun Bin Bingfa (Yinqueshan bamboo slips)")}


def romanize(name: str) -> str:
    from pypinyin import lazy_pinyin

    return "/".join("".join(lazy_pinyin(part)).capitalize() for part in name.split("/"))


MASK = sorted(set("""孔子 仲尼 孔丘 夫子 子曰 孟子 孟轲 荀子 荀卿 孙卿 孙卿子 墨子 子墨子 墨翟 老子 老聃 老君 庄子 庄周
韩非 韩非子 韩子 商君 商鞅 公孙鞅 卫鞅 管子 管仲 夷吾 列子 列御寇 公孙龙 孙子 孙武 孙膑 吴起 吴子 太公 太公望
鬼谷 鬼谷子 黄帝 颜回 颜渊 子路 子贡 曾子 曾参 子思 子夏 子张 子游 冉有 惠子 惠施 杨朱 杨子 申不害 申子 慎到 慎子
尉缭 尉缭子 梁惠王 齐宣王 齐桓公 桓公 晏子 晏婴 子产 告子 万章 公孙丑 滕文公 许行 宋钘 尹文 田骈 邓析 关尹
文王 武王 周公 尧 舜 禹 汤 桀 纣 伯夷 叔齐 盗跖 鲁哀公 哀公 定公 季康子 魏文侯 武侯 威王 力黑 果童 太山之稽
儒者 儒家 墨者 墨家 道家 法家 名家 阴阳家 儒墨 杨墨""".split()), key=len, reverse=True)
MASK_RE = re.compile("|".join(re.escape(m) for m in MASK))


def mask(t: str) -> str:
    return MASK_RE.sub("〇", t)


def read_pairs(d: Path) -> list[tuple[str, str]]:
    bt = d / "bitext.txt"
    pairs: list[tuple[str, str]] = []
    if bt.exists():
        src = None
        for line in bt.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("古文："):
                src = line[3:]
            elif line.startswith("现代文：") and src is not None:
                pairs.append((src, line[4:]))
                src = None
    if not pairs and (d / "source.txt").exists():
        pairs = [(l.strip(), "") for l in (d / "source.txt").read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
    return pairs


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    commit = subprocess.run(["git", "-C", str(SRC.parent), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    rows, meta, prov = [], {}, {"source": "https://github.com/NiuTrans/Classical-Modern", "license": "MIT", "commit": commit, "books": {}}
    for book in TRANSMITTED + SEALED:
        bdir = SRC / book
        if not bdir.exists():
            print("MISSING", book)
            continue
        units = sorted({p.parent for p in bdir.rglob("source.txt")})
        chunks: list[dict] = []
        buf_src, buf_tgt, buf_ch = "", "", []

        def flush():
            nonlocal buf_src, buf_tgt, buf_ch
            if buf_src:
                chunks.append({"chapters": buf_ch, "src": buf_src, "tgt": buf_tgt})
            buf_src, buf_tgt, buf_ch = "", "", []

        h = hashlib.sha256()
        for u in units:
            pairs = read_pairs(u)
            chap = str(u.relative_to(bdir))
            h.update("".join(s for s, _ in pairs).encode())
            unit_len = sum(len(s) for s, _ in pairs)
            if unit_len >= MIN_CHARS:
                flush()  # big chapter: never merged with neighbours, split internally
                cs, ct = "", ""
                for s, t in pairs:
                    if cs and len(cs) + len(s) > MAX_CHARS:
                        chunks.append({"chapters": [chap], "src": cs, "tgt": ct})
                        cs, ct = "", ""
                    cs += s
                    ct += t
                if len(cs) >= MIN_CHARS // 2 or not any(c["chapters"] == [chap] for c in chunks):
                    chunks.append({"chapters": [chap], "src": cs, "tgt": ct})
                elif cs:
                    chunks[-1]["src"] += cs
                    chunks[-1]["tgt"] += ct
            else:  # small unit: merge with following small units of the same book
                for s, t in pairs:
                    buf_src += s
                    buf_tgt += t
                if chap not in buf_ch:
                    buf_ch.append(chap)
                if len(buf_src) >= MAX_CHARS * 0.8:
                    flush()
        flush()
        chunks = [c for c in chunks if len(c["src"]) >= 150]
        for j, c in enumerate(chunks):
            rows.append({"id": f"zh_{len(meta):02d}_{j:03d}", "book": BOOK_EN[book][0], "book_zh": book,
                         "chapters": [romanize(ch) for ch in c["chapters"]], "chapters_zh": c["chapters"],
                         "text": mask(c["src"]), "text_raw": c["src"], "translation": mask(c["tgt"])})
        en = BOOK_EN[book][0]
        meta[en] = {"title": BOOK_EN[book][1], "title_zh": book, "n_units": len(units), "n_chunks": len(chunks),
                    "n_chars": sum(len(c["src"]) for c in chunks), "sealed": book in SEALED}
        prov["books"][en] = {"path": f"双语数据/{book}", "sha256_source_text": h.hexdigest()}
        print(f"{en}\tunits={len(units)}\tchunks={len(chunks)}\tchars={meta[en]['n_chars']}")
    with open(OUT / "chunks.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / "blind.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "text": r["text"]}, ensure_ascii=False) + "\n")
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=1, ensure_ascii=False))
    (OUT / "mask_list.txt").write_text("\n".join(MASK) + "\n")
    print(f"TOTAL {len(rows)} chunks, {len(meta)} books")


if __name__ == "__main__":
    main()
