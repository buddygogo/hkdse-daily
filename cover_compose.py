"""
Typesets the bilingual key message onto an AI background photo, in the style of
Hong Kong news Instagram posts. Text is drawn here, never by the AI, so every
Chinese character is correct. English is the largest line (this is an English
learning site); Traditional Chinese supports it.

Eight layouts, each with its own colour scheme, are rotated by article id so
neighbouring covers never look the same.

article["cover_text"] = {
  "zh_kicker": "白石角站",                     # optional tag
  "zh_title": ["公屋計劃", "臨門變私樓"],        # 1–2 lines, ≤8 characters each
  "zh_hl": "變私樓",                           # part of a title line to emphasise
  "zh_sub": "發展局：區內配套不足",              # one line, ≤14 characters
  "en": "Public flats dropped at Pak Shek Kok rail site"   # 6–10 words
}
"""
import math
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "NotoSansHK-VF.ttf")
W, H = 1080, 1350
M = 60  # outer margin

INK = (21, 25, 34)
WHITE = (255, 255, 255)
YELLOW = (255, 222, 60)
RED = (214, 36, 30)
NAVY = (12, 38, 70)
ORANGE = (255, 122, 26)
CYAN = (70, 214, 255)
DARK = (14, 16, 20)

LINE_COLOURS = {
    "tech": "#0075C2", "school": "#00A650", "env": "#7FA012", "hk": "#E2231A",
    "pop": "#E8479A", "social": "#7D499D", "econ": "#F38B00", "health": "#00888E",
    "global": "#2F8FCB", "urban": "#9A3B26", "law": "#1D3F73", "career": "#5F6F2A",
    "sports": "#C99700", "arts": "#B5307A", "family": "#8C5E3C",
}
TOPIC_ZH = {
    "tech": "科技", "school": "校園", "env": "環境", "hk": "香港文化", "pop": "潮流",
    "social": "社會", "econ": "經濟", "health": "健康", "global": "國際", "urban": "城市發展",
    "law": "法治", "career": "職場", "sports": "體育", "arts": "藝術", "family": "家庭",
}
TOPIC_EN = {
    "tech": "Technology", "school": "School life", "env": "Environment", "hk": "HK culture",
    "pop": "Pop culture", "social": "Society", "econ": "Economy", "health": "Health",
    "global": "Global", "urban": "City", "law": "Law", "career": "Careers", "sports": "Sports",
    "arts": "Arts", "family": "Family",
}

EN_SIZE = 76      # English key message — the largest reading line
ZH_TITLE = 108    # Chinese headline (max; shrinks to fit)
ZH_SUB = 50


# ── helpers ──────────────────────────────────────────────────────────────────

def font(size, weight=900):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_axes([weight])
    return f


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fit(d, text, weight, max_w, start, minimum):
    size = start
    while size > minimum:
        f = font(size, weight)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 3
    return font(minimum, weight)


def wrap(d, text, f, max_w):
    """One line if it fits, else two balanced lines (no lonely last word)."""
    words = text.split()
    if d.textlength(text, font=f) <= max_w or len(words) < 2:
        return [text]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        w = max(d.textlength(a, font=f), d.textlength(b, font=f))
        if best is None or w < best[0]:
            best = (w, [a, b])
    return best[1]


def en_lines(d, text, max_w, size=EN_SIZE, weight=800):
    """Largest size (down to 46) at which the English fits in ≤2 lines."""
    s = size
    while s >= 46:
        f = font(s, weight)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= 2 and all(d.textlength(l, font=f) <= max_w for l in lines):
            return f, lines
        s -= 3
    f = font(46, weight)
    return f, wrap(d, text, f, max_w)[:2]


def cover_crop(img, w, h, focus_y=0.5):
    r = max(w / img.width, h / img.height)
    img = img.resize((math.ceil(img.width * r), math.ceil(img.height * r)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = int((img.height - h) * focus_y)
    return img.crop((x, y, x + w, y + h))


def gradient(w, h, top, bottom):
    g = Image.new("RGB", (w, h), top)
    d = ImageDraw.Draw(g)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g


def shade(img, top_strength=215, top_reach=760, bottom_strength=150, bottom_from=1060):
    """Darken top and/or bottom so white text always reads."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    for y in range(h):
        a = max(0.0, 1 - y / top_reach) ** 1.3 * top_strength if top_reach else 0
        b = max(0.0, (y - bottom_from) / (h - bottom_from)) ** 1.5 * bottom_strength if bottom_from < h else 0
        md.line([(0, y), (w, y)], fill=int(max(a, b)))
    return Image.composite(Image.new("RGB", (w, h), (8, 10, 14)), img, mask)


def title_segments(line, hl):
    if hl and hl in line:
        a, b = line.split(hl, 1)
        return [(a, False), (hl, True), (b, False)]
    return [(line, False)]


def draw_title(d, lines, hl, x, y, max_w, fill, hl_fill, size=ZH_TITLE, stroke=0, stroke_fill=INK,
               hl_box=None, align="left", line_gap=1.1):
    """Stacked Chinese headline; returns the y below it."""
    for line in lines[:2]:
        f = fit(d, line, 900, max_w, size, 70)
        lw = d.textlength(line, font=f)
        cx = x if align == "left" else x + (max_w - lw) / 2
        for text, is_hl in title_segments(line, hl):
            if not text:
                continue
            tw = d.textlength(text, font=f)
            if is_hl and hl_box:
                d.rectangle((cx - 6, y + f.size * 0.12, cx + tw + 6, y + f.size * 1.12), fill=hl_box)
            d.text((cx, y), text, font=f, fill=hl_fill if is_hl else fill,
                   stroke_width=stroke, stroke_fill=stroke_fill)
            cx += tw
        y += int(f.size * line_gap)
    return y


def draw_bar(d, text, x, y, max_w, bg, fg, size=ZH_SUB, weight=800, pad=18):
    f = fit(d, text, weight, max_w - 2 * pad, size, 32)
    tw = d.textlength(text, font=f)
    h = int(f.size * 1.42)
    d.rectangle((x, y, x + tw + 2 * pad, y + h), fill=bg)
    d.text((x + pad, y + int(f.size * 0.1)), text, font=f, fill=fg)
    return y + h


def draw_en(img, d, text, x, y, max_w, fg, bg=None, first_fg=None, size=EN_SIZE, pad=22, alpha=225):
    f, lines = en_lines(d, text, max_w - (2 * pad if bg else 0), size)
    lh = int(f.size * 1.2)
    bh = len(lines) * lh + (2 * pad - 8 if bg else 0)
    if bg:
        block = Image.new("RGBA", (max_w, bh), bg + (alpha,))
        img.paste(block, (x, y), block)
        d = ImageDraw.Draw(img)
    tx, ty = x + (pad if bg else 0), y + (pad - 10 if bg else 0)
    for i, ln in enumerate(lines):
        d.text((tx, ty + i * lh), ln, font=f, fill=(first_fg or fg) if i == 0 else fg)
    return y + bh, d


def draw_mark(d, x_right, y, dark=False):
    """Our own small brand mark (top-right)."""
    f1, f2 = font(28, 800), font(28, 700)
    t1, t2 = "HKDSE Daily", " 每日英語"
    w = d.textlength(t1, font=f1) + d.textlength(t2, font=f2) + 36
    d.rounded_rectangle((x_right - w, y - 6, x_right, y + 44), radius=25, fill=INK if dark else WHITE)
    d.text((x_right - w + 18, y - 1), t1, font=f1, fill=WHITE if dark else INK)
    d.text((x_right - w + 18 + d.textlength(t1, font=f1), y - 1), t2, font=f2, fill=YELLOW if dark else RED)


def draw_date(d, article, x, y, fill=WHITE):
    """Date on its own small pill so it reads on any background."""
    day = (article.get("date") or date.today().isoformat()).replace("-", ".")
    f = font(30, 700)
    w = d.textlength(day, font=f)
    dark = fill == WHITE
    d.rounded_rectangle((x, y - 6, x + w + 32, y + 44), radius=25, fill=(14, 16, 20) if dark else (236, 238, 242))
    d.text((x + 16, y - 1), day, font=f, fill=fill)


def draw_topic(d, cat, x, y, fill=WHITE):
    col = hex2rgb(LINE_COLOURS.get(cat, "#151922"))
    d.ellipse((x, y, x + 44, y + 44), fill=WHITE, outline=col, width=11)
    label = f"{TOPIC_EN.get(cat, '')}  {TOPIC_ZH.get(cat, '')}"
    d.text((x + 58, y - 2), label, font=font(34, 800), fill=fill)


# ── the eight layouts ────────────────────────────────────────────────────────

def L1_classic(bg, a, ct, cat):
    """White stacked headline over the photo, yellow key phrase, red banner."""
    img = shade(cover_crop(bg, W, H), top_reach=800)
    d = ImageDraw.Draw(img)
    draw_date(d, a, M, 58); draw_mark(d, W - M, 58)
    y = 150
    if ct.get("zh_kicker"):
        y = draw_bar(d, ct["zh_kicker"], M, y, 600, RED, WHITE, size=42) + 22
    y, d = draw_en(img, d, ct["en"], M, y, W - 2 * M, WHITE, bg=DARK, first_fg=YELLOW)
    y += 20
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, WHITE, YELLOW, stroke=7)
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], M, y + 6, W - 2 * M, RED, WHITE)
    draw_topic(d, cat, M, H - 104)
    return img


def tint(img, box, rgb, alpha=200, fade=0, fade_dir="up"):
    """Semi-transparent colour panel over the photo; optional soft edge."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    mask = Image.new("L", (w, h), alpha)
    if fade:
        md = ImageDraw.Draw(mask)
        for i in range(fade):
            v = int(alpha * i / fade)
            yy = i if fade_dir == "up" else h - 1 - i
            md.line([(0, yy), (w, yy)], fill=v)
    img.paste(Image.new("RGB", (w, h), rgb), (x0, y0), mask)
    return ImageDraw.Draw(img)


def L2_navy_panel(bg, a, ct, cat):
    """Full-bleed photo; see-through navy panel over the lower half."""
    img = cover_crop(bg, W, H, 0.4)
    d = ImageDraw.Draw(img)
    draw_date(d, a, M, 50); draw_mark(d, W - M, 50)
    panel_y = 600
    d = tint(img, (0, panel_y, W, H), NAVY, alpha=222, fade=90, fade_dir="up")
    d.rectangle((M, panel_y + 96, M + 120, panel_y + 108), fill=YELLOW)
    y = panel_y + 132
    f, lines = en_lines(d, ct["en"], W - 2 * M)
    for i, ln in enumerate(lines):
        d.text((M, y + i * int(f.size * 1.18)), ln, font=f, fill=WHITE)
    y += len(lines) * int(f.size * 1.18) + 24
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, WHITE, YELLOW, size=96)
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], M, y + 4, W - 2 * M, RED, WHITE, size=44)
    draw_topic(d, cat, M, H - 92)
    return img


def L3_paper(bg, a, ct, cat):
    """Full-bleed photo; frosted white panel on top with a big red Chinese headline."""
    img = cover_crop(bg, W, H, 0.7)
    probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
    y = 128 + (84 if ct.get("zh_kicker") else 0)
    y = draw_title(probe, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, RED, INK, size=104)
    f, lines = en_lines(probe, ct["en"], W - 2 * M, size=72)
    panel_h = y + len(lines) * int(f.size * 1.18) + 40
    d = tint(img, (0, 0, W, panel_h), WHITE, alpha=232)
    d.rectangle((0, panel_h, W, panel_h + 10), fill=RED)
    draw_date(d, a, M, 50, fill=INK); draw_mark(d, W - M, 50, dark=True)
    y = 128
    if ct.get("zh_kicker"):
        y = draw_bar(d, ct["zh_kicker"], 0, y, 640, RED, WHITE, size=44, pad=M) + 14
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, RED, INK, size=104)
    for i, ln in enumerate(lines):
        d.text((M, y + i * int(f.size * 1.18)), ln, font=f, fill=INK)
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], M, panel_h + 34, W - 2 * M, INK, YELLOW, size=44)
    d = tint(img, (0, H - 150, W, H), (8, 10, 14), alpha=150, fade=150, fade_dir="up")
    draw_topic(d, cat, M, H - 96)
    return img


def L4_yellow_band(bg, a, ct, cat):
    """Photo full-bleed with a bold yellow band across the middle."""
    img = shade(cover_crop(bg, W, H), top_strength=150, top_reach=420)
    d = ImageDraw.Draw(img)
    draw_date(d, a, M, 58); draw_mark(d, W - M, 58)
    y, d = draw_en(img, d, ct["en"], M, 150, W - 2 * M, WHITE, bg=DARK)
    band_y = y + 40
    tmp = Image.new("RGB", (W, 400)); td = ImageDraw.Draw(tmp)
    end = draw_title(td, ct["zh_title"], ct.get("zh_hl"), M, 24, W - 2 * M, INK, RED, size=104)
    band_h = end + 18
    d.rectangle((0, band_y, W, band_y + band_h), fill=YELLOW)
    draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, band_y + 24, W - 2 * M, INK, RED, size=104)
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], M, band_y + band_h + 18, W - 2 * M, INK, WHITE, size=46)
    draw_topic(d, cat, M, H - 104)
    return img


def L5_dark_polaroid(bg, a, ct, cat):
    """Full-bleed photo darkened, a close-up 'polaroid' crop of it inset at an angle, orange boxes."""
    full = cover_crop(bg, W, H)
    img = Image.composite(Image.new("RGB", (W, H), DARK), full, Image.new("L", (W, H), 150))
    d = ImageDraw.Draw(img)
    draw_date(d, a, M, 58); draw_mark(d, W - M, 58)
    y = 150
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, WHITE, INK, size=100, hl_box=ORANGE)
    y += 10
    f, lines = en_lines(d, ct["en"], W - 2 * M)
    for i, ln in enumerate(lines):
        d.text((M, y + i * int(f.size * 1.2)), ln, font=f, fill=ORANGE if i == 0 else WHITE)
    y += len(lines) * int(f.size * 1.2) + 16
    if ct.get("zh_sub"):
        y = draw_bar(d, ct["zh_sub"], M, y, W - 2 * M, ORANGE, INK, size=44)
    top = y + 40
    avail = H - 130 - top
    if avail > 220:
        ph_h = min(620, avail - 50)
        ph_w = int(ph_h * 1.45)
        # zoomed detail of the same photo, so the inset adds something
        zoom = cover_crop(bg, int(W * 1.5), int(H * 1.5), 0.6)
        zx, zy = (zoom.width - ph_w) // 2, int(zoom.height * 0.55) - ph_h // 2
        photo = zoom.crop((zx, zy, zx + ph_w, zy + ph_h))
        photo = ImageOps.expand(photo, border=16, fill=WHITE).convert("RGBA").rotate(
            -3, expand=True, resample=Image.BICUBIC)
        img.paste(photo, ((W - photo.width) // 2, top), photo)
        d = ImageDraw.Draw(img)
    draw_topic(d, cat, M, H - 96)
    return img


def L6_tech_blue(bg, a, ct, cat):
    """Full-bleed photo; see-through blue gradient over the top, cyan key phrase, yellow banner."""
    img = cover_crop(bg, W, H, 0.6)
    panel_h = 720
    grad = gradient(W, panel_h, (6, 30, 70), (12, 78, 140))
    mask = Image.new("L", (W, panel_h), 0)
    md = ImageDraw.Draw(mask)
    for yy in range(panel_h):
        md.line([(0, yy), (W, yy)], fill=int(228 if yy < panel_h - 140 else 228 * (panel_h - yy) / 140))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 36):  # faint dot grid, a nod to TV news graphics
        for gy in range(0, panel_h - 160, 36):
            d.point((gx, gy), fill=(70, 135, 205))
    draw_date(d, a, M, 50); draw_mark(d, W - M, 50)
    y = 140
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, WHITE, CYAN, size=104)
    y += 6
    f, lines = en_lines(d, ct["en"], W - 2 * M)
    for i, ln in enumerate(lines):
        d.text((M, y + i * int(f.size * 1.18)), ln, font=f, fill=WHITE)
    y += len(lines) * int(f.size * 1.18) + 22
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], 0, y, W, YELLOW, INK, size=46, pad=M)
    d = tint(img, (0, H - 150, W, H), (8, 10, 14), alpha=150, fade=150, fade_dir="up")
    draw_topic(d, cat, M, H - 104)
    return img


def L7_big_number(bg, a, ct, cat):
    """The key number or word set huge in yellow; supporting lines smaller."""
    img = shade(cover_crop(bg, W, H), top_reach=900, top_strength=225)
    d = ImageDraw.Draw(img)
    draw_date(d, a, M, 58); draw_mark(d, W - M, 58)
    hl = ct.get("zh_hl") or ct["zh_title"][0]
    rest = [ln.replace(hl, "").strip() for ln in ct["zh_title"]]
    rest = [r for r in rest if r]
    y = 140
    if ct.get("zh_kicker"):
        y = draw_bar(d, ct["zh_kicker"], M, y, 600, RED, WHITE, size=42) + 10
    big = fit(d, hl, 900, W - 2 * M, 250, 120)
    d.text((M, y), hl, font=big, fill=YELLOW, stroke_width=8, stroke_fill=INK)
    y += int(big.size * 1.08)
    if rest:
        y = draw_title(d, [" ".join(rest)], None, M, y, W - 2 * M, WHITE, WHITE, size=96, stroke=6)
    y, d = draw_en(img, d, ct["en"], M, y + 10, W - 2 * M, WHITE, bg=DARK, first_fg=YELLOW)
    if ct.get("zh_sub"):
        draw_bar(d, ct["zh_sub"], M, y + 14, W - 2 * M, RED, WHITE, size=46)
    draw_topic(d, cat, M, H - 104)
    return img


def L8_topic_strip(bg, a, ct, cat):
    """Bold strip in the topic's line colour; English set large on the colour."""
    col = hex2rgb(LINE_COLOURS.get(cat, "#151922"))
    img = shade(cover_crop(bg, W, H), top_strength=0, top_reach=0, bottom_strength=230, bottom_from=520)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 26, H), fill=col)
    draw_date(d, a, M, 58); draw_mark(d, W - M, 58)
    # measure the stack, then place it at the bottom
    probe = ImageDraw.Draw(Image.new("RGB", (W, 900)))
    f, lines = en_lines(probe, ct["en"], W - 2 * M - 44)
    en_h = len(lines) * int(f.size * 1.2) + 36
    title_end = draw_title(probe, ct["zh_title"], ct.get("zh_hl"), 0, 0, W - 2 * M, WHITE, YELLOW, size=100)
    sub_h = 74 if ct.get("zh_sub") else 0
    y = H - 150 - en_h - 20 - title_end - sub_h
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), M, y, W - 2 * M, WHITE, YELLOW, size=100, stroke=5)
    if ct.get("zh_sub"):
        y = draw_bar(d, ct["zh_sub"], M, y, W - 2 * M, WHITE, INK, size=44) + 20
    d.rectangle((M, y, W - M, y + en_h), fill=col)
    for i, ln in enumerate(lines):
        d.text((M + 22, y + 14 + i * int(f.size * 1.2)), ln, font=f, fill=WHITE)
    draw_topic(d, cat, M, H - 104)
    return img


LAYOUTS = [L1_classic, L2_navy_panel, L3_paper, L4_yellow_band,
           L5_dark_polaroid, L6_tech_blue, L7_big_number, L8_topic_strip]


def layout_for(article):
    if "cover_layout" in article:
        return LAYOUTS[int(article["cover_layout"]) % len(LAYOUTS)]
    return LAYOUTS[int(article.get("id", "a0")[1:], 16) % len(LAYOUTS)]


def compose(bg_path, article, out_path, layout=None):
    ct = dict(article.get("cover_text") or {})
    ct.setdefault("zh_title", [article.get("headline", "")[:8]])
    ct.setdefault("en", article.get("headline", ""))
    cat = (article.get("category") or "social").split()[0]
    bg = Image.open(bg_path).convert("RGB")
    img = (layout or layout_for(article))(bg, article, ct, cat)
    img.save(out_path, "JPEG", quality=86, optimize=True, progressive=True)


# ── wide banners (21:9) for the website's top story ─────────────────────────
BW_, BH_ = 2100, 900


def _banner_text(img, d, a, ct, cat, x, y, max_w, zh_fill, zh_hl, en_fg, en_first, sub_bg, sub_fg,
                 zh_size=118, en_size=84, stroke=0):
    if ct.get("zh_kicker"):
        y = draw_bar(d, ct["zh_kicker"], x, y, 520, RED, WHITE, size=44) + 18
    f, lines = en_lines(d, ct["en"], max_w, size=en_size)
    for i, ln in enumerate(lines):
        d.text((x, y + i * int(f.size * 1.18)), ln, font=f, fill=en_first if i == 0 else en_fg)
    y += len(lines) * int(f.size * 1.18) + 18
    y = draw_title(d, ct["zh_title"], ct.get("zh_hl"), x, y, max_w, zh_fill, zh_hl, size=zh_size, stroke=stroke)
    if ct.get("zh_sub"):
        y = draw_bar(d, ct["zh_sub"], x, y + 6, max_w, sub_bg, sub_fg, size=50)
    return y


def B1_left_fade(bg, a, ct, cat):
    """Photo fills the frame; dark fade from the left carries the text."""
    img = cover_crop(bg, BW_, BH_)
    mask = Image.new("L", (BW_, BH_), 0)
    md = ImageDraw.Draw(mask)
    for x in range(BW_):
        md.line([(x, 0), (x, BH_)], fill=int(max(0.0, 1 - x / 1450) ** 1.1 * 235))
    img = Image.composite(Image.new("RGB", (BW_, BH_), (8, 10, 14)), img, mask)
    d = ImageDraw.Draw(img)
    draw_date(d, a, 80, 60); draw_mark(d, BW_ - 80, 60)
    _banner_text(img, d, a, ct, cat, 80, 160, 1100, WHITE, YELLOW, WHITE, YELLOW, RED, WHITE, stroke=5)
    draw_topic(d, cat, 80, BH_ - 100)
    return img


def B2_bottom_band(bg, a, ct, cat):
    """Photo fills the frame; English on a dark block, Chinese on a yellow band along the bottom."""
    img = cover_crop(bg, BW_, BH_, 0.35)
    d = ImageDraw.Draw(img)
    draw_date(d, a, 80, 60); draw_mark(d, BW_ - 80, 60)
    probe = ImageDraw.Draw(Image.new("RGB", (BW_, 600)))
    title_h = draw_title(probe, [" ".join(ct["zh_title"])], ct.get("zh_hl"), 0, 0, 1500, INK, RED, size=104)
    band_y = BH_ - title_h - 60
    y_en = band_y - 40
    f, lines = en_lines(d, ct["en"], 1500, size=84)
    block_h = len(lines) * int(f.size * 1.18) + 36
    d = tint(img, (80, y_en - block_h, 80 + 1560, y_en), (8, 10, 14), alpha=225)
    for i, ln in enumerate(lines):
        d.text((110, y_en - block_h + 12 + i * int(f.size * 1.18)), ln, font=f, fill=YELLOW if i == 0 else WHITE)
    d.rectangle((0, band_y, BW_, BH_), fill=YELLOW)
    draw_title(d, [" ".join(ct["zh_title"])], ct.get("zh_hl"), 80, band_y + 22, 1500, INK, RED, size=104)
    if ct.get("zh_sub"):
        sf = font(40, 800)
        d.text((BW_ - 80 - d.textlength(ct["zh_sub"], font=sf), band_y + 50), ct["zh_sub"], font=sf, fill=INK)
    return img


def B3_frosted_right(bg, a, ct, cat):
    """Photo fills the frame; frosted white panel on the right with a red Chinese headline."""
    img = cover_crop(bg, BW_, BH_)
    px = 1080
    d = tint(img, (px, 0, BW_, BH_), WHITE, alpha=232)
    d.rectangle((px - 10, 0, px, BH_), fill=RED)
    draw_date(d, a, 80, 60); draw_mark(d, BW_ - 80, 60, dark=True)
    _banner_text(img, d, a, ct, cat, px + 70, 160, BW_ - px - 140, RED, INK, INK, INK, INK, YELLOW,
                 zh_size=110, en_size=78)
    draw_topic(d, cat, 80, BH_ - 100)
    return img


BANNERS = [B1_left_fade, B2_bottom_band, B3_frosted_right]


def compose_banner(bg_path, article, out_path, layout=None):
    ct = dict(article.get("cover_text") or {})
    ct.setdefault("zh_title", [article.get("headline", "")[:8]])
    ct.setdefault("en", article.get("headline", ""))
    cat = (article.get("category") or "social").split()[0]
    bg = Image.open(bg_path).convert("RGB")
    if layout is None:
        layout = BANNERS[int(article.get("id", "a0")[1:], 16) % len(BANNERS)]
    layout(bg, article, ct, cat).save(out_path, "JPEG", quality=86, optimize=True, progressive=True)
