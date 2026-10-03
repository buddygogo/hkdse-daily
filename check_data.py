#!/usr/bin/env python3
"""
Quality gate for new content. Run before merging into archive.json.

    python check_data.py data.json          # a new day's content
    python check_data.py --backfill patch.json

Fails (exit 1) and lists every problem if:
  - an article/trend lacks a Traditional Chinese translation (summary_zh_html)
  - a phrase or vocab item repeats one already used anywhere in the archive,
    in another item of the same batch, or copies the prompt's example phrases
  - a social trend reuses writing-angle labels already used by another trend
  - counts are below the minimums
"""
import json
import re
import sys

ARCHIVE = "archive.json"

# Copied from old prompt examples — never acceptable again
BANNED = {
    "it is widely argued that", "critics contend that", "nevertheless", "by the same token",
    "play a pivotal role in", "digital literacy", "foster critical thinking",
    "psychological appeal", "social media influence", "consumer culture",
    "it is widely reported that",
}
MIN_VOCAB, MIN_PHRASES, MIN_ANGLES = 10, 10, 3
CJK = re.compile(r"[一-鿿]")


def norm(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())


def used_sets(items, skip_ids=()):
    phrases, vocab, angles = {}, {}, {}
    for it in items:
        if it.get("id") in skip_ids or it.get("needs_backfill"):
            continue  # old items that are about to be rewritten don't count
        name = it.get("headline", "")[:50]
        for p in it.get("phrases", []):
            phrases.setdefault(norm(p.get("en")), name)
        for v in it.get("vocab", []):
            vocab.setdefault(norm(v.get("phrase")), name)
        for c in it.get("causes", []):
            angles.setdefault(norm(c.get("label")), name)
    return phrases, vocab, angles


def check(articles, trends, archive, skip_ids=()):
    errs = []
    phrases, vocab, angles = used_sets(archive["articles"] + archive["trends"], skip_ids)

    for a in articles:
        name = a.get("headline", a.get("id", "?"))[:60]
        zh = a.get("summary_zh_html", "")
        if len(CJK.findall(zh)) < 200:
            errs.append(f"[{name}] summary_zh_html missing or too short (need a full Traditional Chinese translation)")
        ps, vs = a.get("phrases", []), a.get("vocab", [])
        if len(ps) < MIN_PHRASES:
            errs.append(f"[{name}] only {len(ps)} phrases (need {MIN_PHRASES}+)")
        if len(vs) < MIN_VOCAB:
            errs.append(f"[{name}] only {len(vs)} vocab items (need {MIN_VOCAB}+)")
        for p in ps:
            k = norm(p.get("en"))
            if k in BANNED:
                errs.append(f"[{name}] phrase '{p.get('en')}' is a banned stock example — write a topic-specific one")
            elif k in phrases:
                errs.append(f"[{name}] phrase '{p.get('en')}' already used in '{phrases[k]}'")
            phrases.setdefault(k, name)
        for v in vs:
            k = norm(v.get("phrase"))
            if k in BANNED:
                errs.append(f"[{name}] vocab '{v.get('phrase')}' is a banned stock example")
            elif k in vocab:
                errs.append(f"[{name}] vocab '{v.get('phrase')}' already used in '{vocab[k]}'")
            vocab.setdefault(k, name)

    for t in trends:
        name = t.get("headline", t.get("id", "?"))[:60]
        if len(CJK.findall(t.get("summary_zh_html", ""))) < 80:
            errs.append(f"[trend {name}] summary_zh_html missing or too short")
        cs = t.get("causes", [])
        if len(cs) < MIN_ANGLES:
            errs.append(f"[trend {name}] only {len(cs)} writing angles (need {MIN_ANGLES}+)")
        for c in cs:
            k = norm(c.get("label"))
            if k in BANNED:
                errs.append(f"[trend {name}] angle '{c.get('label')}' is a banned stock label — name the specific angle")
            elif k in angles:
                errs.append(f"[trend {name}] angle '{c.get('label')}' already used in '{angles[k]}'")
            angles.setdefault(k, name)
            if len((c.get("text") or "").split()) < 25:
                errs.append(f"[trend {name}] angle '{c.get('label')}' explanation too short (25+ words)")
    return errs


def main():
    with open(ARCHIVE, encoding="utf-8") as f:
        archive = json.load(f)
    if sys.argv[1] == "--backfill":
        with open(sys.argv[2], encoding="utf-8") as f:
            patch = json.load(f)
        by_id = {x["id"]: x for x in archive["articles"] + archive["trends"]}
        arts, trs = [], []
        for pid, upd in patch.items():
            if pid not in by_id:
                print(f"unknown id {pid}")
                sys.exit(1)
            merged = {**by_id[pid], **upd}
            (arts if pid.startswith("a") else trs).append(merged)
        errs = check(arts, trs, archive, skip_ids=set(patch))
    else:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
        errs = check(data.get("articles", []), data.get("trends", []), archive)
    if errs:
        print(f"❌ {len(errs)} problem(s):")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print("✅ All checks passed")


if __name__ == "__main__":
    main()
