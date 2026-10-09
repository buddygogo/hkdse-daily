#!/usr/bin/env python3
"""
Write today's image prompts to prompts_today.txt — paste each into the Gemini app
(gemini.google.com), then save the image into the incoming/ folder with the file
name shown. Afterwards run:  python import_covers.py

    python prompts.py          # the 10 newest articles that still need a photo
    python prompts.py 25       # a different number
"""
import json
import os
import subprocess
import sys

from make_covers import build_prompt  # same prompts as the paid API route

HERE = os.path.dirname(os.path.abspath(__file__))
BG = os.path.join(HERE, "covers", "bg")


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=HERE)
    arc = json.load(open(os.path.join(HERE, "archive.json"), encoding="utf-8"))
    arts = sorted(arc["articles"], key=lambda a: a.get("date", ""), reverse=True)
    latest = arts[0].get("date") if arts else ""
    hero = next((a for a in arc["articles"] if a.get("date") == latest), None)

    jobs = []
    if hero and not os.path.exists(os.path.join(BG, f"{hero['id']}_wide.jpg")):
        jobs.append((f"{hero['id']}_wide", "BANNER (wide 21:9) — today's top story", hero, True))
    for a in arts:
        if len([j for j in jobs if not j[3]]) >= limit:
            break
        if not os.path.exists(os.path.join(BG, f"{a['id']}.jpg")):
            jobs.append((a["id"], "COVER (portrait 4:5)", a, False))

    os.makedirs(os.path.join(HERE, "incoming"), exist_ok=True)
    out = [
        "HKDSE Daily — image prompts",
        "For each one: paste the prompt into the Gemini app, download the image,",
        "and save it into the 'incoming' folder with EXACTLY the file name shown",
        "(.jpg or .png both fine). Then run:  python import_covers.py",
        "",
    ]
    for i, (name, kind, a, wide) in enumerate(jobs, 1):
        ratio = "21:9 (very wide landscape)" if wide else "4:5 (portrait)"
        out += [
            "=" * 72,
            f"{i}. Save as:  {name}.jpg      [{kind}]",
            f"   Article:  {a.get('headline', '')}",
            "-" * 72,
            f"Create an image with aspect ratio {ratio}. " + build_prompt(a, wide=wide),
            "",
        ]
    if not jobs:
        out.append("Nothing to do — every article already has a photo.")
    path = os.path.join(HERE, "prompts_today.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Wrote {len(jobs)} prompt(s) to {path}")
    if sys.platform == "win32" and jobs:
        os.startfile(path)


if __name__ == "__main__":
    main()
