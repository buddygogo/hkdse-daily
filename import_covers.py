#!/usr/bin/env python3
"""
Turn the photos you saved from the Gemini app into finished covers and banners,
rebuild the site and upload it to GitHub.

    1. Save images into  incoming/  named  <article id>.jpg  (cover)
       or  <article id>_wide.jpg  (banner) — see prompts_today.txt
    2. python import_covers.py

Covers get their bilingual headline as soon as the article's cover text exists
(written by the backfill/daily routine); until then the photo waits in covers/bg/.
"""
import json
import os
import shutil
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INCOMING = os.path.join(HERE, "incoming")
BG = os.path.join(HERE, "covers", "bg")
ARCHIVE = os.path.join(HERE, "archive.json")
WATERMARK_CROP = 0.06  # trim this share off the bottom and right (Gemini app watermark corner)


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=HERE, check=check, capture_output=True, text=True, encoding="utf-8")


def take_incoming(ids: set[str]) -> int:
    """Move photos from incoming/ into covers/bg/ (cropping the watermark corner)."""
    os.makedirs(BG, exist_ok=True)
    done_dir = os.path.join(INCOMING, "done")
    os.makedirs(done_dir, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(INCOMING)):
        stem, ext = os.path.splitext(f)
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        base = stem[:-5] if stem.endswith("_wide") else stem
        if base not in ids:
            print(f"  ? {f}: no article with id '{base}' — check the file name")
            continue
        img = Image.open(os.path.join(INCOMING, f)).convert("RGB")
        cw, ch = int(img.width * (1 - WATERMARK_CROP)), int(img.height * (1 - WATERMARK_CROP))
        img = img.crop((0, 0, cw, ch))
        img.save(os.path.join(BG, stem + ".jpg"), "JPEG", quality=90)
        shutil.move(os.path.join(INCOMING, f), os.path.join(done_dir, f))
        print(f"  + {f}")
        n += 1
    return n


def typeset(arc: dict) -> tuple[int, int]:
    """Compose every cover/banner whose photo exists and whose cover text has arrived."""
    from cover_compose import compose, compose_banner
    covers = banners = 0
    for a in arc["articles"]:
        if not a.get("cover_text"):
            continue
        p = os.path.join(BG, f"{a['id']}.jpg")
        if os.path.exists(p) and not a.get("cover_typeset"):
            a["cover"] = f"covers/{a['id']}.jpg"
            compose(p, a, os.path.join(HERE, a["cover"]))
            a["cover_typeset"] = True
            covers += 1
        w = os.path.join(BG, f"{a['id']}_wide.jpg")
        if os.path.exists(w) and not a.get("banner"):
            a["banner"] = f"covers/{a['id']}_banner.jpg"
            compose_banner(w, a, os.path.join(HERE, a["banner"]))
            banners += 1
    return covers, banners


def build_and_save(arc: dict) -> None:
    sys.path.insert(0, HERE)
    import generate
    generate.save_archive(arc, ARCHIVE)
    generate._write_index(arc)


def main() -> None:
    print("Getting the latest site from GitHub…")
    git("pull", "-q", "--rebase", "origin", "main", check=False)
    arc = json.load(open(ARCHIVE, encoding="utf-8"))
    print("Photos found:")
    take_incoming({a["id"] for a in arc["articles"]})

    for attempt in range(3):
        arc = json.load(open(ARCHIVE, encoding="utf-8"))
        c, b = typeset(arc)
        waiting = sum(1 for a in arc["articles"]
                      if os.path.exists(os.path.join(BG, f"{a['id']}.jpg")) and not a.get("cover_text"))
        print(f"Typeset {c} cover(s) and {b} banner(s)."
              + (f" {waiting} photo(s) are waiting for their cover text." if waiting else ""))
        build_and_save(arc)
        git("add", "archive.json", "index.html", "a", "covers")
        if git("diff", "--staged", "--quiet", check=False).returncode == 0:
            print("Nothing new to upload.")
            return
        git("commit", "-q", "-m", "Add AI covers made in the Gemini app")
        if git("push", "-q", "origin", "main", check=False).returncode == 0:
            print("Uploaded. The site updates in about a minute: https://buddygogo.github.io/hkdse-daily/")
            return
        # someone else updated the site meanwhile: start again from their version (photos are kept)
        print("The site changed on GitHub while uploading — retrying…")
        keep = os.path.join(HERE, "incoming", "_bg_backup")
        shutil.rmtree(keep, ignore_errors=True)
        shutil.copytree(BG, keep)
        git("fetch", "-q", "origin")
        git("reset", "-q", "--hard", "origin/main")
        shutil.copytree(keep, BG, dirs_exist_ok=True)
        shutil.rmtree(keep, ignore_errors=True)
    print("Upload failed 3 times. Run python import_covers.py again in a few minutes.")


if __name__ == "__main__":
    main()
