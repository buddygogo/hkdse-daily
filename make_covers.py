#!/usr/bin/env python3
"""
AI cover images for every article (Gemini image model). No news-site photos are used.

    python make_covers.py            # make covers for all articles that lack one
    python make_covers.py --limit 3  # just a few (for testing)
    python make_covers.py --redo <id> [<id> ...]

Needs GEMINI_API_KEY in the environment or in a .env file next to this script.
Images are saved as covers/<article id>.jpg and recorded in archive.json as "cover".
"""
import io
import re
import json
import os
import sys
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, "archive.json")
OUT_DIR = os.path.join(HERE, "covers")
BG_DIR = os.path.join(HERE, "covers", "bg")   # text-free AI photos, kept so text can be re-set
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")

# Accent colour per topic (matches the site's "MTR line" colours)
ACCENTS = {
    "tech": "deep blue", "school": "green", "env": "lime green", "hk": "red",
    "pop": "pink", "social": "violet", "econ": "orange", "health": "teal",
    "global": "sky blue", "urban": "brick brown", "law": "navy", "career": "olive",
    "sports": "golden yellow", "arts": "magenta", "family": "warm brown",
}


# (no longer used: compositions are now chosen to fit each story)
SHOTS = [
    "a tight close-up of one telling object on a surface, shallow depth of field",
    "street-level view at eye height in a busy Hong Kong neighbourhood, people as soft motion blur",
    "a straight-down overhead (flat-lay or bird's-eye) view",
    "an interior scene lit by window light, no people",
    "a wide landscape or cityscape taken from low down, with a strong foreground element",
    "a detail of hands at work, cropped at the wrists (no faces)",
    "a symmetrical, head-on architectural view",
    "a night scene lit by practical light sources such as shop signs, lamps or screens",
    "a still life arranged on a table, editorial magazine style",
    "a mid-distance documentary view of a place where the story happens, empty of people",
]


# Stories about harm, death, abuse or arrests get a calm, respectful image instead of an upbeat one
SENSITIVE_WORDS = ("suicide", "self-harm", "death", "dies", "died", "killed", "abuse", "assault", "attack",
                   "arrest", "sedition", "jail", "prison", "murder", "violence", "brawl", "victim", "fatal",
                   "crash", "mauled", "missing", "funeral")
SENSITIVE_STYLE = ("Calm, respectful and quietly hopeful mood: soft natural daylight, gentle warm tones, "
                   "a peaceful symbolic scene (e.g. an empty bench in a garden, morning light through a window, "
                   "a helping hand on a railing). Nothing distressing, violent or sad-looking; no police, "
                   "weapons, injuries, hospital beds or crying. ")


def is_sensitive(article: dict) -> bool:
    text = (article.get("headline", "") + " " + article.get("category", "")).lower()
    return any(w in text for w in SENSITIVE_WORDS)


def _scene(article: dict) -> str:
    """What the picture must show. Prefer the routine's literal scene description;
    otherwise use the article's opening sentences."""
    if article.get("image_scene"):
        return article["image_scene"].strip()
    text = re.sub(r'<span class="tip">.*?</span></span>', "", article.get("summary_html", ""), flags=re.S)
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(sentences[:2])[:600]


def build_prompt(article: dict, wide: bool = False) -> str:
    cat = (article.get("category") or "social").split()[0]
    accent = ACCENTS.get(cat, "red")
    return (
        "Photorealistic editorial news illustration — it must clearly show THIS specific news story, "
        "so a reader instantly understands what happened just by looking at it. "
        f"Headline: {article.get('headline', '')}. "
        f"Show: {_scene(article)} "
        "Depict the actual place, event, activity and key objects of the story as they would look in "
        "Hong Kong (real Hong Kong settings, buildings, streets, venues and details where relevant). "
        "Choose the camera angle and framing that best tells this story, like a news photographer would. "
        + ("Ultra-wide 21:9 panoramic banner: keep the LEFT side calmer and less busy because a headline "
           "will be printed there; place the main action on the right. "
           if wide else
           "Portrait 4:5 for an Instagram news post: keep the TOP part calmer and less busy because a large "
           "headline will be printed over it; place the main action in the lower two-thirds. ")
        + (SENSITIVE_STYLE if is_sensitive(article) else
           "Bright, warm, true-to-life colour: daylight or golden-hour light, rich natural colours, crisp detail, "
           "vivid and engaging for teenagers — never grey, gloomy or blue-tinted. ")
        + f"Where it fits naturally, let {accent} appear as a real colour in the scene. "
        "One single seamless photograph-style image filling the whole frame — no borders, panels, collage or inset images. "
        "People may appear (crowds, staff, athletes, performers, residents) but no recognisable real individuals: "
        "faces turned away, in silhouette, distant or naturally out of focus. "
        "Absolutely NO readable text anywhere: no words, letters or numbers on signs, screens, scoreboards, "
        "banners, papers, clothing or packaging. No logos, no watermarks, no flags."
    )


def make_one(client, article: dict) -> str:
    resp = client.models.generate_content(
        model=MODEL,
        contents=build_prompt(article),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="4:5"),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
            os.makedirs(BG_DIR, exist_ok=True)
            bg = os.path.join(BG_DIR, f"{article['id']}.jpg")
            img.save(bg, "JPEG", quality=90)
            return finish(article) if article.get("cover_text") else None
    raise RuntimeError(f"no image returned (finish_reason={resp.candidates[0].finish_reason})")


def make_banner(client, article: dict) -> str:
    """Wide 21:9 banner for the day's top story (own photo, so it stays sharp)."""
    from cover_compose import compose_banner
    resp = client.models.generate_content(
        model=MODEL,
        contents=build_prompt(article, wide=True),
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="21:9"),
        ),
    )
    for part in resp.candidates[0].content.parts:
        if part.inline_data and part.inline_data.data:
            os.makedirs(BG_DIR, exist_ok=True)
            bg = os.path.join(BG_DIR, f"{article['id']}_wide.jpg")
            Image.open(io.BytesIO(part.inline_data.data)).convert("RGB").save(bg, "JPEG", quality=90)
            rel = f"covers/{article['id']}_banner.jpg"
            compose_banner(bg, article, os.path.join(HERE, rel))
            return rel
    raise RuntimeError(f"no banner returned (finish_reason={resp.candidates[0].finish_reason})")


def finish(article: dict) -> str:
    """Typeset the bilingual headline onto the saved background."""
    from cover_compose import compose
    os.makedirs(OUT_DIR, exist_ok=True)
    rel = f"covers/{article['id']}.jpg"
    compose(os.path.join(BG_DIR, f"{article['id']}.jpg"), article, os.path.join(HERE, rel))
    return rel


def main() -> None:
    load_dotenv(os.path.join(HERE, ".env"))
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY is not set (add it to .env or as the GitHub secret GEMINI_API_KEY) — skipping covers.")
        return
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    redo = set(args[args.index("--redo") + 1:]) if "--redo" in args else set()

    with open(ARCHIVE, encoding="utf-8") as f:
        arc = json.load(f)
    def has_bg(a):
        return os.path.exists(os.path.join(BG_DIR, f"{a['id']}.jpg"))

    # 1) typeset covers whose photo exists and whose cover text has arrived (free, no API call)
    typeset = 0
    for a in arc["articles"]:
        if a.get("id") not in redo and has_bg(a) and a.get("cover_text") and not a.get("cover_typeset"):
            a["cover"] = finish(a)
            a["cover_typeset"] = True
            typeset += 1
    if typeset:
        print(f"Typeset {typeset} cover(s) from existing photos")

    # 2) make photos that are missing (one Gemini image each)
    todo = [a for a in reversed(arc["articles"])  # newest first
            if a.get("id") in redo or (not redo and not has_bg(a))]
    if limit:
        todo = todo[:limit]
    print(f"Making {len(todo)} cover(s) with {MODEL}")

    client = genai.Client()
    made = 0
    for a in todo:
        for attempt in range(3):
            try:
                rel = make_one(client, a)
                if rel:
                    a["cover"], a["cover_typeset"] = rel, True
                made += 1
                print(f"  ✓ {a['id']}  {a.get('headline', '')[:60]}")
                break
            except Exception as e:  # rate limits, transient errors
                msg = str(e)[:160]
                print(f"  … {a['id']} attempt {attempt + 1} failed: {msg}")
                time.sleep(8 * (attempt + 1))
        # save progress after every image so an interruption loses nothing
        with open(ARCHIVE, "w", encoding="utf-8") as f:
            json.dump(arc, f, ensure_ascii=False, indent=1)
    print(f"Done: {made} of {len(todo)} covers made")


if __name__ == "__main__":
    main()
