#!/usr/bin/env python3
"""
HKDSE Daily Brief Generator
════════════════════════════
Self-updating daily news website for HKDSE English Paper 2 students.

Setup:
    pip install anthropic requests beautifulsoup4
    export ANTHROPIC_API_KEY=sk-ant-...

Run:
    python generate.py

Output:
    index.html  ← open in browser or deploy to GitHub Pages

For GitHub Actions automation, see .github/workflows/daily.yml
"""

import os
import sys
import json
import re
import requests
from datetime import date, datetime
from bs4 import BeautifulSoup
import anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────

OUTPUT_FILE = "index.html"
MODEL       = "claude-opus-4-6"

# HKDSE English Language Paper 2 dates.
# Update yearly from: https://www.hkeaa.edu.hk/en/HKDSE/exam_schedule/
# The script will also search for the current/next year's date automatically.
KNOWN_EXAM_DATES: dict[int, date] = {
    2024: date(2024, 4, 24),
    2025: date(2025, 4, 24),
    2026: date(2026, 4, 23),
    2027: date(2027, 4, 22),  # estimated — update when HKEAA publishes
}

# ── EXAM DATE HELPERS ─────────────────────────────────────────────────────────

def get_next_exam_date() -> tuple[date, int, bool]:
    """
    Returns (exam_date, year, is_estimated).
    Finds the next upcoming HKDSE English Paper 2 date.
    """
    today = date.today()
    for year in sorted(KNOWN_EXAM_DATES):
        d = KNOWN_EXAM_DATES[year]
        if d >= today:
            return d, year, False
    # Past all known dates — estimate April 22 of next year
    next_year = today.year + 1
    return date(next_year, 4, 22), next_year, True


# ── IMAGE FETCH ───────────────────────────────────────────────────────────────

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_og_image(url: str, timeout: int = 7) -> str | None:
    """Fetch og:image (or twitter:image) meta tag from an article URL."""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout, allow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")
        for prop in ("og:image", "og:image:secure_url"):
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content", "").startswith("http"):
                return tag["content"]
        for name in ("twitter:image", "twitter:image:src"):
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content", "").startswith("http"):
                return tag["content"]
    except Exception:
        pass
    return None


# ── CONTENT GENERATION PROMPT ─────────────────────────────────────────────────

GENERATION_PROMPT = """\
You are generating content for the HKDSE Daily Brief — a daily English learning resource
for Hong Kong secondary school students preparing for HKDSE Paper 2 (Writing).
Today is {today}.

══ STEP 1a — SEARCH INSTAGRAM ACCOUNTS (OPTIONAL, 0–1 ARTICLE) ══════════════
Optionally search for ONE recent post from either of these two Instagram accounts.
The posts are written in Traditional Chinese — you must translate them into English.

  • hk01news  → search: "hk01news instagram" OR "HK01 新聞 site:instagram.com" OR "hk01.com news today"
  • hk01education → search: "hk01education instagram" OR "HK01 教育 site:instagram.com" OR "hk01.com education today"

If you find a post within the past 48 hours:
  1. Identify the Chinese news story or topic
  2. Find the full original article on hk01.com if possible
  3. Translate the headline and key facts into English
  4. Use this as one article entry with source_name: "HK01 News" or "HK01 Education"

Include AT MOST 1 story from these accounts. If no recent post is found, skip entirely.
The total article count is 4 per day: 0–1 from HK01, 3 from English sources.

══ STEP 1b — SEARCH FOR ENGLISH-SOURCE NEWS (EXACTLY 3 ARTICLES) ════════════
Use web_search to find exactly 3 real, current news articles published in the past 24–48 hours
from English-language sources (in addition to any HK01 article), for a TOTAL of 4 articles. Try:
  • "Hong Kong news today"
  • "Hong Kong education technology 2026"
  • "Hong Kong environment policy 2026"
  • "Hong Kong social issues today"
  • "Hong Kong pop culture trend"
  • "Hong Kong economy inflation 2026"
  • "Hong Kong public health 2026"
  • "Hong Kong housing urban development 2026"
  • "Hong Kong global affairs 2026"
  • "Hong Kong career jobs youth 2026"
  • "Hong Kong law crime 2026"
  • "Hong Kong sports achievement 2026"
  • "Hong Kong arts culture 2026"
  • "Hong Kong media journalism 2026"
  • "Hong Kong family elderly 2026"

Prefer English sources ONLY here: South China Morning Post, RTHK, The Standard, Mingpao English.
Aim for variety — do not repeat the same topic as the HK01 articles above.
Topics to cover (pick varied topics each day, ensure no two articles share the same category):
  • School life, education policy, student wellbeing, learning
  • Technology, AI, social media, digital life
  • Pop culture (K-pop, C-pop, entertainment, gaming, fashion)
  • HK culture & tradition (heritage, festivals, identity, food culture)
  • Social trends & issues (mental health, youth, inequality, consumer behaviour)
  • Environment (climate, pollution, sustainability, green policy)
  • Economy & finance (inflation, cost of living, job market, business)
  • Health & medicine (public health, mental health, medical innovation, wellbeing)
  • Global affairs & geopolitics (international relations, trade, diplomacy)
  • Urban development & housing (smart city, infrastructure, transport, property)
  • Law, justice & ethics (crime trends, legal reform, social justice, rights)
  • Career & future of work (employment, skills gap, AI in workplace, entrepreneurship)
  • Sports & fitness (HK athletes, youth sport, wellness trends)
  • Arts, media & journalism (film, music, publishing, press freedom)
  • Family & society (elderly care, parenting, gender, community)

══ STEP 2 — SEARCH FOR SOCIAL MEDIA TRENDS ═══════════════════════════════════
Use web_search to find 1–2 current Hong Kong social media trends. Try:
  • "Hong Kong TikTok trend 2026"
  • "viral Hong Kong social media today"
  • "trending Hong Kong Instagram 2026"
  • "Hong Kong youth trend 2026"

Examples of good trends: blind box collecting, viral food trends, new K-pop/C-pop moments,
viral challenges, new consumer product waves, gaming trends, fashion trends.

══ STEP 3 — SEARCH FOR HKDSE EXAM DATE ═══════════════════════════════════════
Search: "HKDSE {next_year} English Language exam date timetable site:hkeaa.edu.hk"
and also: "HKDSE {next_year} exam timetable English Paper 2"
If you find a confirmed date for Paper 2 (Writing), include it. Otherwise return null.

══ OUTPUT FORMAT ══════════════════════════════════════════════════════════════
Return ONLY a valid JSON object. No markdown fences. No explanation. Just JSON.

{{
  "exam_date": "YYYY-MM-DD or null",
  "articles": [
    {{
      "source_name": "HK01 News",
      "source_url": "https://www.hk01.com/...",
      "published_date": "9 June 2026",
      "headline": "English translation of the Chinese headline",
      "category": "tech",
      "summary_html": "...(see writing rules below)...",
      "vocab": [
        {{
          "phrase": "uncritical reliance on",
          "zh": "不加批判地依賴……",
          "sample": "Students must guard against uncritical reliance on social media for news."
        }}
      ],
      "phrases": [
        {{"en": "uncritical reliance", "zh": "不加批判的依賴", "sample": "An uncritical reliance on technology may undermine students' independent thinking skills."}},
        {{"en": "alleviate pressure", "zh": "減輕壓力", "sample": "Policymakers must introduce measures to alleviate pressure on young people in a highly competitive society."}}
      ],
      "writing_angles": [
        {{
          "label": "Psychological dimension",
          "zh_label": "心理層面",
          "text": "The <span class=\"bw\">compulsive need<span class=\"tip\"><span class=\"tip-en\">an irresistible urge driven by anxiety or habit</span><span class=\"tip-zh\">強迫性需求</span></span></span> to stay informed may trigger <span class=\"bw\">information overload<span class=\"tip\"><span class=\"tip-en\">the state of being overwhelmed by excessive data</span><span class=\"tip-zh\">資訊過載</span></span></span>, paradoxically reducing critical engagement and increasing anxiety among young readers."
        }},
        {{
          "label": "Sociological dimension",
          "zh_label": "社會學層面",
          "text": "<span class=\"bw\">Peer influence<span class=\"tip\"><span class=\"tip-en\">pressure from people of the same age group</span><span class=\"tip-zh\">同儕影響</span></span></span> and the desire for <span class=\"bw\">social validation<span class=\"tip\"><span class=\"tip-en\">approval and acceptance from others</span><span class=\"tip-zh\">社會認同</span></span></span> drive conformist behaviour, as individuals adopt attitudes and habits primarily to align with the dominant norms of their social circle."
        }},
        {{
          "label": "Economic dimension",
          "zh_label": "經濟層面",
          "text": "The <span class=\"bw\">commodification<span class=\"tip\"><span class=\"tip-en\">the process of turning something into a product to be bought and sold</span><span class=\"tip-zh\">商品化</span></span></span> of attention has created a system in which <span class=\"bw\">vested commercial interests<span class=\"tip\"><span class=\"tip-en\">businesses with a financial stake in influencing behaviour</span><span class=\"tip-zh\">既得商業利益</span></span></span> profit from prolonged engagement, often at the expense of users' wellbeing."
        }},
        {{
          "label": "Policy dimension",
          "zh_label": "政策層面",
          "text": "In the absence of <span class=\"bw\">regulatory oversight<span class=\"tip\"><span class=\"tip-en\">government supervision to ensure rules are followed</span><span class=\"tip-zh\">監管</span></span></span>, <span class=\"bw\">self-regulatory mechanisms<span class=\"tip\"><span class=\"tip-en\">voluntary rules set by an industry to govern itself</span><span class=\"tip-zh\">自我監管機制</span></span></span> have proven inadequate to protect vulnerable groups, making binding legislation an urgent necessity."
        }}
      ]
    }}
  ],
  "trends": [
    {{
      "platforms": ["tiktok", "ig"],
      "headline": "🎁 The Blind Box Craze Sweeps Hong Kong",
      "summary_html": "...(see writing rules below)...",
      "causes": [
        {{"label": "Dopamine and uncertainty", "text": "The random outcome activates the brain's reward system..."}}
      ]
    }}
  ]
}}

══ TRANSLATION RULES (for HK01 / Chinese-source articles) ════════════════════
When an article originates from hk01news or hk01education (or any Chinese-language source):
  • Translate the headline into natural, idiomatic English (not word-for-word)
  • Write the summary_html entirely in English — no Chinese in the body text
  • The vocab zh field and phrases zh field should still be Traditional Chinese as normal
  • The English summary must be original prose, not a translation dump —
    write it as a HKDSE Paper 2 model paragraph from the start

══ WRITING RULES ══════════════════════════════════════════════════════════════

summary_html for articles (150–220 words):
- Formal HKDSE Paper 2 essay style: complex sentences, hedging, discourse markers
- Use: "It is widely argued that…", "Critics contend that…", "Nevertheless,",
  "By the same token,", "One cannot deny that…", "It is worth noting that…"
- Bold 6–10 key phrases using EXACTLY this span structure (no IPA pronunciation anywhere):
    <span class="bw">key phrase<span class="tip"><span class="tip-en">English definition</span><span class="tip-zh">釋義（繁體）</span></span></span>
- Surround paragraphs with <p> tags

summary_html for articles (250–300 words, MINIMUM 120 words):
- Each article must have at least 120 words. Target 250 words average.
- Use at least 3–4 paragraphs for full development

summary_html for trends (100–150 words):
- Same tooltip format as above

vocab: 10–12 items per article
- phrase: the English phrase (DO NOT number them)
- zh: Traditional Chinese characters only — no romanisation, no pronunciation
- sample: full HKDSE-quality sentence using the phrase in a meaningful, exam-relevant context

phrases: 10–15 rows for quick-reference table
- en: English phrase or expression
- zh: Traditional Chinese only — no romanisation, no pronunciation
- sample: one DSE-style sentence demonstrating the phrase in context

causes: 4–5 items per trend
- label: short title
- text: 1–2 sentences as HKDSE writing angle (sociological, psychological, economic, technological)

writing_angles: 4–5 items per article (REQUIRED for every article)
- label: short angle title in English (e.g. "Psychological dimension", "Economic dimension")
- zh_label: Traditional Chinese translation of the label (e.g. "心理層面", "經濟層面")
- text: 2–3 sentences of DSE-quality analytical writing on this angle. Use the SAME tooltip span
  format as summary_html to bold 2–4 key analytical terms:
    <span class="bw">key term<span class="tip"><span class="tip-en">English definition</span><span class="tip-zh">繁體中文釋義</span></span></span>
  Cover a mix of: psychological / sociological / economic / political / technological / ethical / cultural angles.
  Each angle must be a distinct analytical lens — no overlap between angles.

category: one of tech / school / env / hk / pop / social / econ / health / global / urban / law / career / sports / arts / family
  (space-separated if multiple, e.g. "tech school")
platforms: array of: tiktok / ig / threads / fb
"""


# ── CONTENT GENERATION ───────────────────────────────────────────────────────

def generate_content() -> dict:
    """Call Claude with web search to generate today's HKDSE content."""
    client = anthropic.Anthropic()

    try:
        tz = __import__("zoneinfo").ZoneInfo("Asia/Hong_Kong")
    except ImportError:
        try:
            import pytz
            tz = pytz.timezone("Asia/Hong_Kong")
        except ImportError:
            tz = None

    now   = datetime.now(tz=tz) if tz else datetime.utcnow()
    today = now.strftime("%A, %d %B %Y")
    next_year = now.year + 1

    prompt = GENERATION_PROMPT.format(today=today, next_year=next_year)

    print("  🔍 Searching news and trends with Claude…")

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract final text block
    raw = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            raw += block.text

    # Strip markdown code fences if present
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\n?```\s*$",          "", raw, flags=re.MULTILINE)
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to pull JSON out of any surrounding text
        m = re.search(r"\{[\s\S]+\}", raw)
        if m:
            return json.loads(m.group())
        print("⚠  Could not parse JSON. Raw response:")
        print(raw[:800])
        sys.exit(1)


# ── HTML BUILDING ─────────────────────────────────────────────────────────────
# Everything below this line controls the page appearance only.
# The API / generation logic above is unchanged.

_TAG_META = {
    "tech":   ("tag-tech",   "Technology"),
    "school": ("tag-school", "School Life"),
    "env":    ("tag-env",    "Environment"),
    "hk":     ("tag-hk",    "HK Culture"),
    "pop":    ("tag-pop",    "Pop Culture"),
    "social": ("tag-social", "Social Trends"),
    "econ":   ("tag-econ",  "Economy"),
    "health": ("tag-health", "Health"),
    "global": ("tag-global", "Global Affairs"),
    "urban":  ("tag-urban",  "Urban Dev"),
    "law":    ("tag-law",   "Law & Justice"),
    "career": ("tag-career", "Career"),
    "sports": ("tag-sports", "Sports"),
    "arts":   ("tag-arts",  "Arts & Media"),
    "family": ("tag-family", "Family & Society"),
}

_TAG_EMOJI = {
    "tech": "🖥", "school": "📚", "env": "🌿", "hk": "🏮", "pop": "🎵",
    "social": "📊", "econ": "💰", "health": "🏥", "global": "🌍", "urban": "🏗",
    "law": "⚖️", "career": "🎓", "sports": "🏅", "arts": "🎨", "family": "👨‍👩‍👧",
}

_PLATFORM_META = {
    "tiktok":  ("pt-tiktok",  "TikTok"),
    "ig":      ("pt-ig",      "Instagram"),
    "threads": ("pt-threads", "Threads"),
    "fb":      ("pt-fb",      "Facebook"),
}

# Source names that originated from Instagram — shown with IG badge
_INSTAGRAM_SOURCES = {"HK01 News", "HK01 Education"}

# Designed fallback covers — used when an article has no photo yet
_COVER_GRADIENTS = {
    "tech":   ("#1d3b8f", "#3aa0ff"), "school": ("#5b2a86", "#b46cf0"),
    "env":    ("#14532d", "#4fbf6b"), "hk":     ("#8a1c1c", "#e8663d"),
    "pop":    ("#9d174d", "#f472b6"), "social": ("#334155", "#7c93b8"),
    "econ":   ("#7a5a00", "#e0b12e"), "health": ("#0f5e63", "#34c3b5"),
    "global": ("#0b3d5c", "#3b9cc9"), "urban":  ("#3f3f46", "#a1a1aa"),
    "law":    ("#3b2f1e", "#a0825a"), "career": ("#1e3a5f", "#5b8fd6"),
    "sports": ("#9a3412", "#fb923c"), "arts":   ("#6b1d5c", "#d45fb4"),
    "family": ("#7c2d12", "#f59e6b"),
}


# Each topic is an "MTR line" with its own colour
_LINE_COLOURS = {
    "tech": "#0075C2", "school": "#00A650", "env": "#9BB21B", "hk": "#E2231A",
    "pop": "#E8479A", "social": "#7D499D", "econ": "#F38B00", "health": "#00888E",
    "global": "#4BA8DE", "urban": "#9A3B26", "law": "#1D3F73", "career": "#5F6F2A",
    "sports": "#D9A400", "arts": "#B5307A", "family": "#8C5E3C",
}


def build_route_strip(articles: list[dict], trends: list[dict]) -> str:
    counts = {}
    for a in articles:
        counts[_first_cat(a)] = counts.get(_first_cat(a), 0) + 1
    stops = [f'<button class="line-stop active" data-cat="all" onclick="filterCards(\'all\',this)" style="--line:#151922">'
             f'<span class="stop-dot"></span><span class="stop-name">All topics</span></button>']
    if trends:
        stops.append(f'<button class="line-stop" data-cat="trends" onclick="filterCards(\'trends\',this)" style="--line:#D7261E">'
                     f'<span class="stop-dot"></span><span class="stop-name">Social trends</span></button>')
    for cat in _CAT_ORDER:
        lbl = _TAG_META.get(cat, ("", cat))[1]
        n = counts.get(cat, 0)
        stops.append(f'<button class="line-stop{" empty" if not n else ""}" data-cat="{cat}" onclick="filterCards(\'{cat}\',this)" '
                     f'style="--line:{_LINE_COLOURS[cat]}"><span class="stop-dot"></span>'
                     f'<span class="stop-name">{lbl}</span></button>')
    return "".join(stops)


def _first_cat(article: dict) -> str:
    cats = (article.get("category") or "social").split()
    return cats[0] if cats else "social"


def _cover_html(article: dict, image_url: str | None, img_cls: str, wrap_fallback_cls: str) -> str:
    """Real photo if we have one, with a designed topic cover behind it as fallback."""
    cat = _first_cat(article)
    c1, c2 = _COVER_GRADIENTS.get(cat, ("#1e293b", "#475569"))
    emoji = _TAG_EMOJI.get(cat, "📰")
    label = _TAG_META.get(cat, ("", "News"))[1]
    fallback = (
        f'<div class="cover-fallback {wrap_fallback_cls}" style="background:linear-gradient(135deg,{c1},{c2})">'
        f'<span class="cover-emoji">{emoji}</span><span class="cover-label">{label}</span></div>'
    )
    url = article.get("cover")  # AI-generated cover (make_covers.py); news-site photos are never used
    if not url:
        return fallback
    safe = url.replace('"', '%22')
    alt = (article.get("headline") or "").replace('"', '')
    return (
        f'{fallback}<img class="{img_cls}" src="{safe}" alt="{alt}" loading="lazy" '
        f'onerror="this.remove()">'
    )


def _causes_html(causes: list[dict]) -> str:
    """DSE writing angles: English label + text with 🔊, Chinese translation underneath."""
    items = ""
    for c in causes:
        label, text = c.get("label", ""), c.get("text", "")
        lzh, tzh = c.get("label_zh", ""), c.get("text_zh", "")
        items += f"""
          <li class="angle">
            <div class="angle-head"><strong>{label}</strong>
              <button class="speak-btn" onclick="speak('{_speak(label + '. ' + text)}')" title="Listen">🔊</button>
              {f'<span class="angle-zh-label">{lzh}</span>' if lzh else ''}</div>
            <div class="angle-text">{text}</div>
            {f'<div class="angle-zh" lang="zh-Hant">{tzh}</div>' if tzh else ''}
          </li>"""
    return f"""
        <div class="causes-block">
          <div class="causes-title">DSE writing angles 寫作角度</div>
          <ul class="causes-list">{items}</ul>
        </div>"""


def _actions_html(uid: str) -> str:
    """Print / share buttons shown at the bottom of each article."""
    return f"""
      <div class="article-actions">
        <button class="act-btn" onclick="printArticle('{uid}', 'both')">🖨 Print</button>
        <button class="act-btn" onclick="listenArticle('{uid}', this)">🔊 Listen</button>
        <button class="act-btn act-share" onclick="shareArticle('{uid}')">Share</button>
      </div>"""


def _nice_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%-d %b %Y") if os.name != "nt" else date.fromisoformat(iso).strftime("%#d %b %Y")
    except (ValueError, TypeError):
        return iso or ""


def _number_marks(html: str, cls: str) -> str:
    """<span class="bw"> → <span class="bw" data-k="1">, in order of appearance."""
    n = 0
    def tag(_m):
        nonlocal n
        n += 1
        return f'<span class="{cls}" data-k="{n}">'
    return re.sub(rf'<span class=(?:\\?)"{cls}(?:\\?)">', tag, html or "")


def _bilingual_html(en_html: str, zh_html: str, en_cls: str = "news-body") -> str:
    """English article on the left, Traditional Chinese translation on the right.
    The Nth highlighted English phrase (.bw) is paired with the Nth Chinese one (.bwz)."""
    en_html = _number_marks(en_html, "bw")
    zh_html = _number_marks(zh_html, "bwz")
    if not zh_html:
        return f'<div class="{en_cls}">{en_html}</div>'
    return f"""
      <div class="bi-grid">
        <div class="bi-col bi-en {en_cls}"><div class="bi-label">English</div>{en_html}</div>
        <div class="bi-col bi-zh" lang="zh-Hant"><div class="bi-label">中文翻譯</div>{zh_html}</div>
      </div>"""


def _source_badge(source_name: str) -> str:
    """Return an Instagram badge span if the source came from Instagram."""
    if source_name in _INSTAGRAM_SOURCES:
        return '<span class="ig-source-badge">📸 Instagram</span>'
    return ""


def _speak(text: str) -> str:
    """Escape single quotes for inline onclick."""
    return text.replace("'", "\\'")


def _study_notes_html(article: dict, uid: str) -> str:
    """Collapsible study notes block (vocab + phrase table)."""
    vocab_html = ""
    for i, v in enumerate(article.get("vocab", []), 1):
        phrase  = v.get("phrase", "")
        zh      = v.get("zh", "")
        sample  = v.get("sample", "")
        ph_esc  = _speak(phrase)
        zh_esc  = _speak(zh)
        smp_esc = _speak(sample)
        vocab_html += f"""
        <div class="vocab-item">
          <div class="vocab-phrase">
            <span class="vocab-num">{i}</span>
            {phrase}
            <button class="speak-btn" onclick="speak('{ph_esc}')">🔊</button>
            <button class="save-vocab-btn" title="Save to My List"
              onclick="saveVocab('{ph_esc}','{zh_esc}','{smp_esc}',this)">💾</button>
          </div>
          <div class="vocab-zh">{zh}</div>
          <div class="vocab-sample">"{sample}"</div>
        </div>"""

    rows_html = ""
    for p in article.get("phrases", []):
        en     = p.get("en", "")
        zh     = p.get("zh", "")
        sample = p.get("sample", "")
        en_esc = _speak(en)
        zh_esc = _speak(zh)
        sm_esc = _speak(sample)
        rows_html += f"""
        <tr>
          <td class="en-col">{en}
            <button class="speak-btn-sm" onclick="speak('{en_esc}')">🔊</button>
            <button class="save-vocab-btn-sm" title="Save"
              onclick="saveVocab('{en_esc}','{zh_esc}','{sm_esc}',this)">💾</button>
          </td>
          <td class="zh-col">{zh}</td>
          <td class="sample-col"><em>{sample}</em></td>
        </tr>"""

    # Writing angles
    angles_html = ""
    for angle in article.get("writing_angles", []):
        label    = angle.get("label", "")
        zh_label = angle.get("zh_label", "")
        text     = angle.get("text", "")
        # strip HTML tags to make a plain-text saveable version
        text_plain = re.sub(r"<[^>]+>", "", text)
        lbl_esc  = _speak(label)
        zh_esc   = _speak(zh_label)
        txt_esc  = _speak(text_plain[:300])
        angles_html += f"""
        <li class="writing-angle-item">
          <div class="writing-angle-header">
            <span class="writing-angle-label">{label}</span>
            <span class="writing-angle-zh">{zh_label}</span>
            <button class="save-vocab-btn-sm" title="Save writing angle"
              onclick="saveVocab('{lbl_esc}','{zh_esc}','{txt_esc}',this)">💾</button>
          </div>
          <div class="writing-angle-text">{text}</div>
        </li>"""

    angles_block = ""
    if angles_html:
        angles_block = f"""
      <div class="vocab-section-label" style="margin-top:1.4rem;">✍️ DSE Writing Angles</div>
      <ul class="writing-angles-list">{angles_html}</ul>"""

    note_key = article.get("id") or uid
    return f"""
    <div class="study-toggle" onclick="toggleStudy('{uid}')">
      <span class="study-toggle-label">📖 Study Notes</span>
      <span class="study-toggle-icon" id="icon-{uid}">▾</span>
    </div>
    <div class="study-drawer" id="drawer-{uid}">
      <div class="vocab-section-label">Key Vocabulary</div>
      <div class="vocab-grid">{vocab_html}</div>
      <div class="vocab-section-label" style="margin-top:1.2rem;">Quick Reference — Phrases &amp; Sample Sentences</div>
      <div class="phrase-table-wrap">
        <table class="phrase-table">
          <thead><tr><th>Phrase / Expression</th><th>釋義</th><th>DSE Sample Sentence</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>{angles_block}
      <div class="article-note-section" data-note="{note_key}">
        <div class="note-label">✏️ My Notes</div>
        <p class="note-login-hint">
          <button onclick="signInWithGoogle()">Sign in with Google</button> to save personal notes for this article
        </p>
        <textarea class="note-textarea" placeholder="Write your own notes, essay ideas, or vocabulary reminders here…"></textarea>
        <div class="note-save-row">
          <button class="note-save-btn" onclick="saveNote('{note_key}', this)">Save note</button>
          <span class="note-status"></span>
        </div>
      </div>
    </div>"""


def build_hero_html(article: dict, image_url: str | None, uid: str) -> str:
    """First article rendered as a full-width hero card."""
    cats     = article.get("category", "social").split()
    data_cat = " ".join(cats)
    first_cat = cats[0] if cats else "social"
    tag_cls  = _TAG_META.get(first_cat, ("tag-social", "Social"))[0]
    tag_lbl  = _TAG_META.get(first_cat, ("tag-social", "Social"))[1]
    tag_em   = _TAG_EMOJI.get(first_cat, "📰")

    src_name = article.get("source_name", "Source")
    src_url  = article.get("source_url",  "#")
    pub      = article.get("published_date", "")
    ig_badge = _source_badge(src_name)

    img_html = _cover_html(article, image_url, "hero-img", "cover-hero")
    if article.get("banner"):  # wide 21:9 banner for the top story, when one exists
        alt = (article.get("headline") or "").replace('"', '')
        img_html = f'<img class="hero-img" src="{article["banner"]}" alt="{alt}" onerror="this.remove()">'
    top_cls = "hero-top has-banner" if article.get("banner") else "hero-top"

    study = _study_notes_html(article, uid)

    hl_esc = article.get('headline','').replace("'", "&#39;")

    return f"""
  <article class="hero-card" data-cat="{data_cat}">
    <div class="{top_cls}">
      <div class="hero-media" onclick="openFull('{uid}')">
        {img_html}
      </div>
      <div class="hero-head">
        <span class="cat-chip {tag_cls}" style="--line:{_LINE_COLOURS.get(first_cat, '#151922')}">{tag_lbl}</span>
        <h2 class="hero-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{article.get('headline','')}</h2>
        <div class="hero-byline" id="meta-{uid}">
          <a class="hero-source" href="{src_url}" target="_blank" rel="noopener">{src_name}</a>
          {ig_badge}
          {f'<span class="hero-dot">·</span><span class="hero-pub">{pub}</span>' if pub else ''}
        </div>
        <p class="hero-excerpt">{_excerpt(article.get('summary_html', ''), 60)}</p>
      </div>
    </div>
    <div class="hero-body" id="body-{uid}">
      {_bilingual_html(article.get('summary_html',''), article.get('summary_zh_html',''))}
      {study}
      {_actions_html(uid)}
    </div>
  </article>"""


_FRAGMENTS: dict[str, str] = {}   # a/<id>.html files written next to index.html


def _excerpt(html: str, words: int = 38) -> str:
    text = re.sub(r"<span class=\"tip\">.*?</span></span>", "", html or "", flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    parts = text.split(" ")
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def build_article_card_html(article: dict, image_url: str | None, uid: str, lazy: bool = False) -> str:
    """Grid card. lazy=True keeps only a preview in the page; full text loads from a/<id>.html."""
    cats     = article.get("category", "social").split()
    data_cat = " ".join(cats)
    first_cat = cats[0] if cats else "social"
    tag_cls  = _TAG_META.get(first_cat, ("tag-social", "Social"))[0]
    tag_lbl  = _TAG_META.get(first_cat, ("tag-social", "Social"))[1]
    tag_em   = _TAG_EMOJI.get(first_cat, "📰")

    src_name = article.get("source_name", "Source")
    src_url  = article.get("source_url",  "#")
    pub      = article.get("published_date", "")
    ig_badge = _source_badge(src_name)

    img_html = f'<div class="card-thumb-wrap" onclick="openFull(\'{uid}\')">{_cover_html(article, image_url, "card-thumb", "cover-card")}</div>'

    full_body = (
        _bilingual_html(article.get('summary_html', ''), article.get('summary_zh_html', ''), 'card-summary news-body')
        + _study_notes_html(article, uid)
        + _actions_html(uid)
    )
    if lazy:
        _FRAGMENTS[uid] = full_body
        body_html = (f'<div id="body-{uid}" data-src="a/{uid}.html">'
                     f'<p class="card-summary card-excerpt" onclick="openFull(\'{uid}\')">{_excerpt(article.get("summary_html", ""))}</p></div>')
    else:
        body_html = f'<div id="body-{uid}">{full_body}</div>'
    date_chip = f'<span class="card-dot">·</span><span class="card-pub">{_nice_date(article["date"])}</span>' if lazy and article.get("date") else (
        f'<span class="card-dot">·</span><span class="card-pub">{pub}</span>' if pub else '')

    return f"""
  <article class="article-card" data-cat="{data_cat}">
    {img_html}
    <div class="card-body">
      <span class="cat-chip {tag_cls}" style="--line:{_LINE_COLOURS.get(first_cat, '#151922')}">{tag_lbl}</span>
      <h3 class="card-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{article.get('headline','')}</h3>
      <div class="card-meta" id="meta-{uid}">
        <a class="card-source" href="{src_url}" target="_blank" rel="noopener">{src_name}</a>
        {ig_badge}
        {date_chip}
      </div>
      {body_html}
    </div>
  </article>"""


def _trend_notes(trend: dict, uid: str) -> str:
    """Trends get the same study notes as articles once they have vocab/phrases."""
    if not (trend.get("vocab") or trend.get("phrases")):
        return ""
    return _study_notes_html(trend, uid + "-n")


def build_trend_sidebar_html(trend: dict, idx: int) -> str:
    """Trend rendered as a compact sidebar item."""
    plat_html = "".join(
        f'<span class="platform-tag {_PLATFORM_META.get(p, ("pt-fb",""))[0]}">'
        f'{_PLATFORM_META.get(p, ("pt-fb", p.upper()))[1]}</span>'
        for p in trend.get("platforms", [])
    )
    causes_html = "".join(
        f'<li><strong>{c.get("label","")}:</strong> {c.get("text","")}</li>'
        for c in trend.get("causes", [])
    )
    uid = "s" + (trend.get("id") or f"trend-{idx}")  # 's' prefix: sidebar copy, avoids ID clash with the main feed
    return f"""
  <div class="trend-item" data-cat="social pop">
    <div class="trend-item-platforms">{plat_html}</div>
    <h4 class="trend-item-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{trend.get('headline','')}</h4>
    <div class="trend-study-toggle" onclick="toggleStudy('{uid}')">
      <span>Full analysis</span><span id="icon-{uid}">▾</span>
    </div>
    <div id="meta-{uid}" style="display:none"><span>Social Trend</span></div>
    <div id="body-{uid}">
      <div class="study-drawer" id="drawer-{uid}">
        {_bilingual_html(trend.get('summary_html',''), trend.get('summary_zh_html',''), 'trend-body')}
        {_causes_html(trend.get("causes", []))}
        {_trend_notes(trend, uid)}
        {_actions_html(uid)}
      </div>
    </div>
  </div>"""


def build_trend_main_html(trends: list[dict]) -> str:
    """Renders social trends as a full-width main-feed section."""
    if not trends:
        return ""
    items_html = ""
    for idx, trend in enumerate(trends):
        uid = trend.get("id") or f"trend-{idx}"
        plat_html = "".join(
            f'<span class="platform-tag {_PLATFORM_META.get(p, ("pt-fb",""))[0]}">'
            f'{_PLATFORM_META.get(p, ("pt-fb", p.upper()))[1]}</span>'
            for p in trend.get("platforms", [])
        )
        causes_html = "".join(
            f'<li><strong>{c.get("label","")}:</strong> {c.get("text","")}</li>'
            for c in trend.get("causes", [])
        )
        items_html += f"""
  <div class="trend-main-item article-card" data-cat="trends social pop">
    <div class="trend-item-platforms">{plat_html}</div>
    <h3 class="trend-main-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{trend.get('headline','')}</h3>
    <div class="card-meta" id="meta-{uid}"><span>Social Trend</span>{f'<span class="card-dot">·</span><span class="card-pub">{_nice_date(trend.get("date",""))}</span>' if trend.get("date") else ''}</div>
    <div id="body-{uid}">
      {_bilingual_html(trend.get('summary_html',''), trend.get('summary_zh_html',''), 'trend-body')}
      {_causes_html(trend.get("causes", []))}
      {_trend_notes(trend, uid)}
      {_actions_html(uid)}
    </div>
    <button class="read-more-btn" onclick="openFull('{uid}')">Read trend + 4 essay angles</button>
  </div>"""
    return f"""
  <div class="main-section-head" data-cat="trends">
    <h2>Social trends</h2>
    <span class="section-see-all">Four essay angles for each trend</span>
  </div>
  <div class="articles-grid trends-grid" data-cat="trends">
    {items_html}
  </div>"""


def build_countdown_widget_html(exam_date: date, is_estimated: bool) -> str:
    """Countdown as a right-sidebar widget."""
    date_iso = exam_date.isoformat()
    est_note = " (est.)" if is_estimated else ""
    return f"""
  <div class="countdown-widget">
    <div class="countdown-widget-label">⏳ Paper 2{est_note}</div>
    <div class="countdown-widget-date" id="exam-date-display">Loading…</div>
    <div class="countdown-widget-ring">
      <span class="countdown-days" id="countdown-days">--</span>
      <span class="countdown-unit" id="countdown-unit">days</span>
    </div>
    <div class="countdown-widget-tip">One article a day. 加油！</div>
    <script>
    (function() {{
      var EXAM = new Date("{date_iso}T00:00:00+08:00");
      document.getElementById('exam-date-display').textContent =
        EXAM.toLocaleDateString('en-HK', {{month:'long', day:'numeric', year:'numeric', timeZone:'Asia/Hong_Kong'}});
      function tick() {{
        var diff = Math.ceil((EXAM - new Date()) / 86400000);
        var dEl = document.getElementById('countdown-days');
        var uEl = document.getElementById('countdown-unit');
        if (diff > 1)       {{ dEl.textContent = diff;    uEl.textContent = 'days to go'; }}
        else if (diff === 1){{ dEl.textContent = '1';     uEl.textContent = 'day to go!'; }}
        else if (diff === 0){{ dEl.textContent = 'TODAY'; uEl.textContent = 'Good luck!'; }}
        else                {{ dEl.textContent = '✓';     uEl.textContent = 'complete'; }}
      }}
      tick(); setInterval(tick, 60000);
    }})();
    </script>
  </div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
    /* ── TOKENS — LIGHT (default) ── */
    :root {
      --bg:      #f7f8fa;
      --surface: #ffffff;
      --border:  #e8eaed;
      --ink:     #111827;
      --sub:     #374151;
      --muted:   #6b7280;
      --faint:   #f3f4f6;
      --accent:  #1d4ed8;
      --accent-hover: #1e40af;
      --accent-light: #eff6ff;
      --sidebar-active: #eff6ff;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04);
      --shadow-md: 0 4px 16px rgba(0,0,0,0.09), 0 1px 4px rgba(0,0,0,0.05);

      /* tag colors — text / bg */
      --t-tech:   #1d4ed8; --tb-tech:   #eff6ff;
      --t-school: #065f46; --tb-school: #ecfdf5;
      --t-env:    #0f766e; --tb-env:    #f0fdfa;
      --t-hk:     #92400e; --tb-hk:     #fffbeb;
      --t-pop:    #9d174d; --tb-pop:    #fdf2f8;
      --t-social: #5b21b6; --tb-social: #f5f3ff;
      --t-econ:   #78350f; --tb-econ:   #fff7ed;
      --t-health: #065f46; --tb-health: #ecfdf5;
      --t-global: #164e63; --tb-global: #ecfeff;
      --t-urban:  #374151; --tb-urban:  #f3f4f6;
      --t-law:    #881337; --tb-law:    #fff1f2;
      --t-career: #4c1d95; --tb-career: #faf5ff;
      --t-sports: #9a3412; --tb-sports: #fff7ed;
      --t-arts:   #831843; --tb-arts:   #fdf2f8;
      --t-family: #713f12; --tb-family: #fefce8;
    }

    /* ── TOKENS — DARK (system preference, no explicit stamp) ── */
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --bg:      #0e1117;
        --surface: #161b27;
        --border:  #252d3d;
        --ink:     #f1f5f9;
        --sub:     #cbd5e1;
        --muted:   #64748b;
        --faint:   #1a2035;
        --accent:  #60a5fa;
        --accent-hover: #93c5fd;
        --accent-light: #1e3a5f;
        --sidebar-active: #1e3a5f;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
        --t-tech:   #93c5fd; --tb-tech:   #1e3a5f;
        --t-school: #6ee7b7; --tb-school: #064e3b;
        --t-env:    #5eead4; --tb-env:    #134e4a;
        --t-hk:     #fcd34d; --tb-hk:     #451a03;
        --t-pop:    #f9a8d4; --tb-pop:    #500724;
        --t-social: #c4b5fd; --tb-social: #2e1065;
        --t-econ:   #fdba74; --tb-econ:   #431407;
        --t-health: #6ee7b7; --tb-health: #064e3b;
        --t-global: #67e8f9; --tb-global: #083344;
        --t-urban:  #94a3b8; --tb-urban:  #1e293b;
        --t-law:    #fda4af; --tb-law:    #4c0519;
        --t-career: #ddd6fe; --tb-career: #2e1065;
        --t-sports: #fed7aa; --tb-sports: #431407;
        --t-arts:   #fbcfe8; --tb-arts:   #500724;
        --t-family: #fef08a; --tb-family: #422006;
      }
    }
    /* ── explicit dark stamp ── */
    :root[data-theme="dark"] {
      --bg:      #0e1117;
      --surface: #161b27;
      --border:  #252d3d;
      --ink:     #f1f5f9;
      --sub:     #cbd5e1;
      --muted:   #64748b;
      --faint:   #1a2035;
      --accent:  #60a5fa;
      --accent-hover: #93c5fd;
      --accent-light: #1e3a5f;
      --sidebar-active: #1e3a5f;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
      --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
      --t-tech:   #93c5fd; --tb-tech:   #1e3a5f;
      --t-school: #6ee7b7; --tb-school: #064e3b;
      --t-env:    #5eead4; --tb-env:    #134e4a;
      --t-hk:     #fcd34d; --tb-hk:     #451a03;
      --t-pop:    #f9a8d4; --tb-pop:    #500724;
      --t-social: #c4b5fd; --tb-social: #2e1065;
      --t-econ:   #fdba74; --tb-econ:   #431407;
      --t-health: #6ee7b7; --tb-health: #064e3b;
      --t-global: #67e8f9; --tb-global: #083344;
      --t-urban:  #94a3b8; --tb-urban:  #1e293b;
      --t-law:    #fda4af; --tb-law:    #4c0519;
      --t-career: #ddd6fe; --tb-career: #2e1065;
      --t-sports: #fed7aa; --tb-sports: #431407;
      --t-arts:   #fbcfe8; --tb-arts:   #500724;
      --t-family: #fef08a; --tb-family: #422006;
    }

    /* ── RESET ── */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'DM Sans', 'Inter', sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }
    a { color: inherit; text-decoration: none; }
    button { cursor: pointer; font-family: inherit; }

    /* ── TOPBAR ── */
    .topbar {
      position: sticky; top: 0; z-index: 200;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      box-shadow: var(--shadow-sm);
    }
    .topbar-inner {
      max-width: 1280px; margin: 0 auto;
      display: flex; align-items: center; gap: 0;
      padding: 0 1.5rem; height: 54px;
    }
    .logo {
      display: flex; align-items: center; gap: 0.55rem;
      flex-shrink: 0; margin-right: 2rem;
    }
    .logo-mark {
      width: 30px; height: 30px; border-radius: 7px;
      background: var(--ink);
      display: flex; align-items: center; justify-content: center;
      font-size: 0.9rem;
    }
    .logo-name {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 1.2rem; color: var(--ink); letter-spacing: -0.02em;
    }
    .topbar-nav {
      display: flex; align-items: center; gap: 0; flex: 1;
      overflow-x: auto; scrollbar-width: none;
    }
    .topbar-nav::-webkit-scrollbar { display: none; }
    .nav-tab {
      flex-shrink: 0; padding: 0 1rem; height: 54px;
      display: flex; align-items: center;
      font-size: 0.82rem; font-weight: 500; color: var(--muted);
      border-bottom: 2px solid transparent;
      background: none; border-top: none; border-left: none; border-right: none;
      transition: color 0.15s, border-color 0.15s;
      white-space: nowrap;
    }
    .nav-tab:hover { color: var(--ink); }
    .nav-tab.active { color: var(--ink); border-bottom-color: var(--ink); font-weight: 600; }
    .topbar-right {
      display: flex; align-items: center; gap: 0.75rem;
      margin-left: auto; flex-shrink: 0;
    }
    .topbar-date { font-size: 0.75rem; color: var(--muted); white-space: nowrap; }
    .topbar-date strong { display: block; color: var(--ink); font-size: 0.82rem; }
    .live-badge {
      display: inline-flex; align-items: center; gap: 0.35rem;
      background: #dcfce7; color: #15803d;
      font-size: 0.67rem; font-weight: 700;
      padding: 0.18rem 0.6rem; border-radius: 20px;
    }
    .live-dot {
      width: 5px; height: 5px; background: #16a34a;
      border-radius: 50%; animation: pulse 1.5s infinite;
    }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

    /* ── 3-COLUMN LAYOUT ── */
    .site-body {
      max-width: 1280px; margin: 0 auto;
      display: grid;
      grid-template-columns: 200px 1fr 272px;
      gap: 0;
      min-height: calc(100vh - 54px);
    }

    /* ── LEFT SIDEBAR ── */
    .left-sidebar {
      border-right: 1px solid var(--border);
      padding: 1.5rem 0;
      position: sticky; top: 54px;
      height: calc(100vh - 54px); overflow-y: auto;
      scrollbar-width: thin;
    }
    .sidebar-section-label {
      font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted);
      padding: 0 1rem 0.5rem; margin-top: 1rem;
    }
    .sidebar-link {
      display: flex; align-items: center; gap: 0.55rem;
      padding: 0.5rem 1rem; font-size: 0.82rem; color: var(--sub);
      border-radius: 0; background: none; border: none; width: 100%;
      text-align: left; transition: background 0.12s, color 0.12s;
      cursor: pointer;
    }
    .sidebar-link:hover { background: var(--faint); color: var(--ink); }
    .sidebar-link.active {
      background: var(--sidebar-active);
      color: var(--accent); font-weight: 600;
    }
    .sidebar-link .sl-icon { font-size: 0.9rem; width: 1.1rem; text-align: center; flex-shrink: 0; }
    .sidebar-divider { height: 1px; background: var(--border); margin: 0.75rem 0; }

    /* ── MAIN CONTENT ── */
    .main-content {
      padding: 1.5rem 1.75rem;
      min-width: 0;
    }
    .main-section-head {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 1rem; padding-bottom: 0.6rem;
      border-bottom: 1px solid var(--border);
    }
    .main-section-head h2 {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 1.05rem; color: var(--ink); letter-spacing: -0.01em;
    }
    .section-see-all {
      font-size: 0.75rem; color: var(--accent); font-weight: 600;
    }

    /* ── HERO CARD ── */
    .hero-card {
      border-radius: 12px; overflow: hidden;
      background: var(--surface);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-sm);
      margin-bottom: 1.5rem;
      transition: box-shadow 0.2s;
    }
    .hero-card:hover { box-shadow: var(--shadow-md); }
    .hero-media { position: relative; aspect-ratio: 16/7; overflow: hidden; background: #111; }
    .hero-img {
      width: 100%; height: 100%; object-fit: cover; display: block;
      transition: transform 0.4s ease;
    }
    .hero-card:hover .hero-img { transform: scale(1.02); }
    .hero-img-placeholder {
      width: 100%; height: 100%;
      background: linear-gradient(135deg, #1e293b, #0f172a);
    }
    .hero-overlay {
      position: absolute; inset: 0;
      background: linear-gradient(to top, rgba(0,0,0,0.82) 0%, rgba(0,0,0,0.3) 50%, transparent 100%);
    }
    .hero-overlay-text {
      position: absolute; bottom: 0; left: 0; right: 0;
      padding: 1.2rem 1.4rem;
    }
    .hero-headline {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 1.45rem; color: #fff; line-height: 1.35;
      text-wrap: balance; margin: 0.45rem 0 0.55rem;
    }
    .hero-byline {
      display: flex; align-items: center; gap: 0.4rem;
      font-size: 0.75rem; color: rgba(255,255,255,0.7);
    }
    .hero-source { color: #93c5fd; font-weight: 600; }
    .hero-source:hover { color: #fff; }
    .hero-dot { color: rgba(255,255,255,0.4); }
    .hero-body { padding: 1.2rem 1.4rem; }

    /* ── ARTICLE GRID ── */
    .articles-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .article-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; overflow: hidden;
      display: flex; flex-direction: column;
      transition: box-shadow 0.2s, transform 0.2s;
    }
    .article-card:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
    .card-thumb-wrap { aspect-ratio: 3/2; overflow: hidden; background: var(--faint); }
    .card-thumb { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 0.3s ease; }
    .article-card:hover .card-thumb { transform: scale(1.04); }
    .card-body { padding: 0.9rem 1rem; flex: 1; display: flex; flex-direction: column; gap: 0.45rem; }
    .card-headline {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 0.97rem; color: var(--ink); line-height: 1.4;
      text-wrap: balance;
    }
    .card-meta { display: flex; align-items: center; gap: 0.35rem; flex-wrap: wrap; }
    .card-source { font-size: 0.7rem; font-weight: 600; color: var(--accent); }
    .card-source:hover { color: var(--accent-hover); }
    .card-dot { color: var(--border); font-size: 0.7rem; }
    .card-pub { font-size: 0.7rem; color: var(--muted); }
    .card-summary { font-size: 0.83rem; color: var(--sub); line-height: 1.7; }
    .card-summary p + p { margin-top: 0.6rem; }

    /* ── CATEGORY CHIP ── */
    .cat-chip {
      display: inline-block; font-size: 0.65rem; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.05em;
      padding: 0.18rem 0.55rem; border-radius: 4px;
    }
    .tag-tech   { color: var(--t-tech);   background: var(--tb-tech); }
    .tag-school { color: var(--t-school); background: var(--tb-school); }
    .tag-env    { color: var(--t-env);    background: var(--tb-env); }
    .tag-hk     { color: var(--t-hk);    background: var(--tb-hk); }
    .tag-pop    { color: var(--t-pop);    background: var(--tb-pop); }
    .tag-social { color: var(--t-social); background: var(--tb-social); }
    .tag-econ   { color: var(--t-econ);   background: var(--tb-econ); }
    .tag-health { color: var(--t-health); background: var(--tb-health); }
    .tag-global { color: var(--t-global); background: var(--tb-global); }
    .tag-urban  { color: var(--t-urban);  background: var(--tb-urban); }
    .tag-law    { color: var(--t-law);    background: var(--tb-law); }
    .tag-career { color: var(--t-career); background: var(--tb-career); }
    .tag-sports { color: var(--t-sports); background: var(--tb-sports); }
    .tag-arts   { color: var(--t-arts);   background: var(--tb-arts); }
    .tag-family { color: var(--t-family); background: var(--tb-family); }

    /* ── INSTAGRAM SOURCE BADGE ── */
    .ig-source-badge {
      display: inline-flex; align-items: center; gap: 0.2rem;
      font-size: 0.62rem; font-weight: 700;
      padding: 0.12rem 0.45rem; border-radius: 20px;
      background: linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888);
      color: #fff; vertical-align: middle; margin-left: 0.2rem;
      letter-spacing: 0.03em;
    }

    /* ── STUDY NOTES ACCORDION ── */
    .study-toggle {
      display: flex; align-items: center; justify-content: space-between;
      margin-top: 0.8rem; padding: 0.55rem 0.8rem;
      background: var(--faint); border: 1px solid var(--border);
      border-radius: 7px; cursor: pointer;
      transition: background 0.15s;
    }
    .study-toggle:hover { background: var(--accent-light); }
    .study-toggle-label { font-size: 0.75rem; font-weight: 600; color: var(--accent); }
    .study-toggle-icon { font-size: 0.75rem; color: var(--muted); transition: transform 0.2s; }
    .study-toggle-icon.open { transform: rotate(180deg); }
    .study-drawer { display: none; margin-top: 0.75rem; }
    .study-drawer.open { display: block; }
    .trend-study-toggle {
      display: flex; align-items: center; justify-content: space-between;
      margin-top: 0.5rem; font-size: 0.72rem; color: var(--accent);
      cursor: pointer; font-weight: 600;
    }
    .trend-study-toggle:hover { color: var(--accent-hover); }
    .vocab-section-label {
      font-size: 0.67rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); margin-bottom: 0.6rem;
    }
    .vocab-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 0.6rem;
    }
    .vocab-item {
      background: var(--accent-light); border: 1px solid rgba(29,78,216,0.1);
      border-radius: 8px; padding: 0.7rem 0.85rem;
    }
    .vocab-phrase {
      font-weight: 700; font-size: 0.82rem; color: var(--accent);
      display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap;
      margin-bottom: 0.2rem;
    }
    .vocab-num {
      background: var(--accent); color: #fff;
      font-size: 0.58rem; font-weight: 700;
      width: 15px; height: 15px; border-radius: 50%;
      display: inline-flex; align-items: center; justify-content: center;
      flex-shrink: 0; font-variant-numeric: tabular-nums;
    }
    .vocab-zh { font-family: 'Noto Sans HK', sans-serif; font-size: 0.75rem; color: var(--sub); }
    .vocab-sample {
      font-size: 0.82rem; color: var(--muted); font-style: italic;
      margin-top: 0.35rem; padding-top: 0.35rem;
      border-top: 1px dashed var(--border); line-height: 1.6;
    }
    .phrase-table-wrap { overflow-x: auto; margin-top: 0.5rem; }
    .phrase-table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
    .phrase-table th {
      background: var(--ink); color: rgba(255,255,255,0.75);
      font-size: 0.63rem; text-transform: uppercase; letter-spacing: 0.07em;
      padding: 0.45rem 0.8rem; text-align: left;
    }
    .phrase-table td { padding: 0.45rem 0.8rem; border-bottom: 1px solid var(--border); vertical-align: top; }
    .phrase-table tr:last-child td { border-bottom: none; }
    .phrase-table tr:nth-child(even) td { background: var(--faint); }
    .phrase-table tr:hover td { background: var(--accent-light); }
    .en-col { font-weight: 600; color: var(--ink); min-width: 160px; }
    .zh-col { font-family: 'Noto Sans HK', sans-serif; color: var(--sub); min-width: 110px; }
    .sample-col { font-size: 0.78rem; color: var(--muted); font-style: italic; line-height: 1.5; }

    /* ── SAVE VOCAB BUTTONS ── */
    .save-vocab-btn, .save-vocab-btn-sm {
      background: none; border: 1px solid var(--border);
      border-radius: 20px; cursor: pointer; color: var(--muted);
      font-size: 0.65rem; padding: 0.08rem 0.4rem; margin-left: 0.2rem;
      vertical-align: middle; transition: color 0.15s, border-color 0.15s, transform 0.15s;
    }
    .save-vocab-btn:hover, .save-vocab-btn-sm:hover { color: var(--accent); border-color: var(--accent); transform: scale(1.1); }
    .save-vocab-btn.saved, .save-vocab-btn-sm.saved { color: #16a34a; border-color: #16a34a; }
    .save-vocab-btn-sm { font-size: 0.58rem; padding: 0.05rem 0.3rem; }

    /* ── SAVED VOCAB PANEL ── */
    .saved-panel-overlay {
      display: none; position: fixed; inset: 0; z-index: 500;
      background: rgba(0,0,0,0.45); backdrop-filter: blur(2px);
    }
    .saved-panel-overlay.open { display: flex; align-items: flex-start; justify-content: flex-end; }
    .saved-panel {
      width: min(520px, 95vw); height: 100vh; overflow-y: auto;
      background: var(--surface); border-left: 1px solid var(--border);
      box-shadow: -4px 0 32px rgba(0,0,0,0.15);
      display: flex; flex-direction: column;
    }
    .saved-panel-head {
      padding: 1.1rem 1.3rem; border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
      position: sticky; top: 0; background: var(--surface); z-index: 10;
    }
    .saved-panel-title {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 1.1rem; color: var(--ink);
    }
    .saved-panel-actions { display: flex; gap: 0.6rem; align-items: center; }
    .saved-panel-close {
      background: none; border: none; font-size: 1.2rem; color: var(--muted); cursor: pointer;
      padding: 0.1rem 0.4rem;
    }
    .saved-panel-close:hover { color: var(--ink); }
    .btn-print-saved {
      display: inline-flex; align-items: center; gap: 0.35rem;
      background: var(--accent); color: #fff;
      border: none; border-radius: 7px; padding: 0.4rem 0.85rem;
      font-size: 0.78rem; font-weight: 600; cursor: pointer;
      transition: background 0.15s;
    }
    .btn-print-saved:hover { background: var(--accent-hover); }
    .btn-clear-saved {
      background: none; border: 1px solid var(--border); border-radius: 7px;
      padding: 0.4rem 0.75rem; font-size: 0.75rem; color: var(--muted); cursor: pointer;
    }
    .btn-clear-saved:hover { border-color: #dc2626; color: #dc2626; }
    .saved-panel-body { padding: 1rem 1.3rem; flex: 1; }
    .saved-empty { text-align: center; padding: 3rem 1rem; color: var(--muted); font-size: 0.88rem; }
    .saved-vocab-item {
      border: 1px solid var(--border); border-radius: 9px; padding: 0.8rem 1rem;
      margin-bottom: 0.7rem; background: var(--faint); position: relative;
    }
    .saved-vocab-phrase { font-weight: 700; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.25rem; }
    .saved-vocab-zh { font-family: 'Noto Sans HK', sans-serif; font-size: 0.78rem; color: var(--sub); margin-bottom: 0.3rem; }
    .saved-vocab-sample { font-size: 0.82rem; color: var(--muted); font-style: italic; line-height: 1.55; }
    .saved-vocab-remove {
      position: absolute; top: 0.55rem; right: 0.7rem;
      background: none; border: none; cursor: pointer; font-size: 0.8rem;
      color: var(--muted); opacity: 0.6;
    }
    .saved-vocab-remove:hover { opacity: 1; color: #dc2626; }
    .saved-count-badge {
      display: inline-flex; align-items: center; justify-content: center;
      background: var(--accent); color: #fff;
      font-size: 0.6rem; font-weight: 700;
      min-width: 16px; height: 16px; border-radius: 50%; padding: 0 3px;
      margin-left: 0.3rem; vertical-align: middle;
    }
    .saved-count-badge:empty { display: none; }
    .btn-open-saved {
      display: inline-flex; align-items: center; gap: 0.3rem;
      background: var(--faint); border: 1px solid var(--border); border-radius: 20px;
      padding: 0.3rem 0.75rem; font-size: 0.75rem; font-weight: 600;
      color: var(--sub); cursor: pointer; transition: background 0.15s, color 0.15s;
    }
    .btn-open-saved:hover { background: var(--accent-light); color: var(--accent); }
    .btn-print-page {
      display: inline-flex; align-items: center; gap: 0.3rem;
      background: var(--faint); border: 1px solid var(--border); border-radius: 20px;
      padding: 0.3rem 0.75rem; font-size: 0.75rem; font-weight: 600;
      color: var(--sub); cursor: pointer; transition: background 0.15s, color 0.15s;
    }
    .btn-print-page:hover { background: var(--faint); color: var(--ink); }

    /* ── TOOLTIP ── */
    .bw {
      font-weight: 700; color: var(--accent);
      border-bottom: 2px dotted var(--accent);
      cursor: help; position: relative; display: inline;
    }
    .bw .tip {
      display: none; position: absolute;
      bottom: calc(100% + 8px); left: 50%;
      transform: translateX(-50%);
      background: var(--ink); color: var(--surface);
      border-radius: 8px; padding: 0.6rem 0.85rem; width: 230px;
      font-size: 0.73rem; font-weight: 400; line-height: 1.6;
      z-index: 999; pointer-events: none;
      box-shadow: var(--shadow-md);
    }
    .bw .tip::after {
      content: ''; position: absolute; top: 100%; left: 50%;
      transform: translateX(-50%);
      border: 6px solid transparent; border-top-color: var(--ink);
    }
    .bw:hover .tip { display: block; }
    .tip-en { color: #93c5fd; font-style: italic; display: block; }
    .tip-zh { font-family: 'Noto Sans HK', sans-serif; color: #6ee7b7; display: block; margin-top: 3px; }

    /* ── SPEAK BUTTONS ── */
    .speak-btn, .speak-btn-sm {
      background: none; border: 1px solid var(--accent);
      border-radius: 20px; cursor: pointer; color: var(--accent);
      opacity: 0.6; vertical-align: middle; line-height: 1;
      font-size: 0.68rem; padding: 0.1rem 0.45rem; margin-left: 0.25rem;
      transition: opacity 0.15s, transform 0.15s;
    }
    .speak-btn-sm { font-size: 0.6rem; padding: 0.07rem 0.35rem; }
    .speak-btn:hover, .speak-btn-sm:hover { opacity: 1; transform: scale(1.12); }

    /* ── NEWS BODY (shared) ── */
    .news-body { font-size: 0.88rem; color: var(--sub); line-height: 1.85; }
    .news-body p + p { margin-top: 0.7rem; }

    /* ── RIGHT SIDEBAR ── */
    .right-sidebar {
      border-left: 1px solid var(--border);
      padding: 1.5rem 1rem;
      position: sticky; top: 54px;
      height: calc(100vh - 54px); overflow-y: auto;
      scrollbar-width: thin;
    }
    .sidebar-widget-head {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 0.9rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }
    .sidebar-widget-head h3 {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 0.95rem; color: var(--ink);
    }
    .sidebar-see-all { font-size: 0.72rem; color: var(--accent); font-weight: 600; }

    /* ── TREND ITEMS ── */
    .trend-item {
      padding: 0.85rem 0;
      border-bottom: 1px solid var(--border);
    }
    .trend-item:last-of-type { border-bottom: none; }
    .trend-item-platforms { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-bottom: 0.4rem; }
    .platform-tag {
      font-size: 0.6rem; font-weight: 700; padding: 0.15rem 0.5rem;
      border-radius: 20px; text-transform: uppercase; letter-spacing: 0.05em;
    }
    .pt-tiktok  { background: #010101; color: #fff; }
    .pt-ig      { background: linear-gradient(135deg,#f09433,#e6683c,#dc2743,#cc2366,#bc1888); color: #fff; }
    .pt-threads { background: #000; color: #fff; }
    .pt-fb      { background: #1877f2; color: #fff; }
    .trend-item-headline {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 0.88rem; color: var(--ink); line-height: 1.4;
      text-wrap: balance;
    }
    .trend-body { font-size: 0.8rem; color: var(--sub); line-height: 1.7; margin-bottom: 0.7rem; }
    .causes-block {
      background: var(--faint); border-radius: 7px;
      padding: 0.7rem 0.85rem; margin-top: 0.5rem;
    }
    .causes-title {
      font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); margin-bottom: 0.45rem;
    }
    .causes-list { list-style: none; display: flex; flex-direction: column; gap: 0.3rem; }
    .causes-list li {
      font-size: 0.78rem; color: var(--sub); padding-left: 1.1rem;
      position: relative; line-height: 1.5;
    }
    .causes-list li::before { content: '▸'; position: absolute; left: 0; color: var(--accent); }

    /* ── COUNTDOWN WIDGET ── */
    .countdown-widget {
      margin-top: 1.4rem; padding-top: 1.4rem;
      border-top: 1px solid var(--border); text-align: center;
    }
    .countdown-widget-label {
      font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.4rem;
    }
    .countdown-widget-date { font-size: 0.78rem; color: var(--sub); margin-bottom: 1rem; }
    .countdown-widget-ring {
      display: inline-flex; flex-direction: column;
      align-items: center; justify-content: center;
      width: 110px; height: 110px; border-radius: 50%;
      border: 2px solid var(--border);
      background: var(--surface);
      box-shadow: var(--shadow-sm);
      margin-bottom: 0.7rem;
    }
    .countdown-days {
      font-family: 'DM Serif Display', Georgia, serif;
      font-size: 2.4rem; color: var(--ink); line-height: 1;
      font-variant-numeric: tabular-nums;
    }
    .countdown-unit { font-size: 0.6rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.2rem; }
    .countdown-widget-tip { font-size: 0.72rem; color: var(--muted); font-style: italic; }

    /* ── FOOTER ── */
    footer {
      grid-column: 1 / -1; text-align: center;
      padding: 1.5rem; font-size: 0.72rem; color: var(--muted);
      border-top: 1px solid var(--border); background: var(--surface);
      font-family: 'Noto Sans HK', sans-serif;
    }

    /* ── WRITING ANGLES ── */
    .writing-angles-list {
      list-style: none; display: flex; flex-direction: column; gap: 0.6rem;
      margin-top: 0.5rem;
    }
    .writing-angle-item {
      background: var(--faint); border: 1px solid var(--border);
      border-left: 3px solid var(--accent);
      border-radius: 0 8px 8px 0; padding: 0.65rem 0.9rem;
    }
    .writing-angle-header {
      display: flex; align-items: center; gap: 0.5rem;
      flex-wrap: wrap; margin-bottom: 0.35rem;
    }
    .writing-angle-label {
      font-weight: 700; font-size: 0.8rem; color: var(--accent);
    }
    .writing-angle-zh {
      font-family: 'Noto Sans HK', sans-serif; font-size: 0.72rem;
      color: var(--muted); border-left: 1px solid var(--border);
      padding-left: 0.45rem; margin-left: 0.1rem;
    }
    .writing-angle-text {
      font-size: 0.82rem; color: var(--sub); line-height: 1.75;
    }

    /* ── PRINT STYLES ── */
    @media print {
      .topbar, .left-sidebar, .right-sidebar, .study-toggle,
      .speak-btn, .speak-btn-sm, .save-vocab-btn, .save-vocab-btn-sm,
      .saved-panel-overlay, footer, .btn-print-page, .btn-open-saved { display: none !important; }
      .site-body { display: block; max-width: 100%; }
      .main-content { padding: 0; }
      .hero-media { aspect-ratio: auto; max-height: 200px; }
      .hero-overlay-text { position: static; padding: 0.5rem 0; }
      .hero-headline { color: #000; font-size: 1.2rem; }
      .hero-body { padding: 0.5rem 0; }
      .articles-grid { display: block; }
      .article-card { border: 1px solid #ddd; margin-bottom: 1rem; break-inside: avoid; }
      .study-drawer { display: block !important; }
      .vocab-grid { grid-template-columns: 1fr 1fr; }
      .vocab-item { background: #f9f9f9; border: 1px solid #ddd; }
      .bw { color: #000; border-bottom: 1px solid #999; }
      .bw .tip { display: none !important; }
      body { color: #000; background: #fff; font-size: 11pt; }
      a { color: #000; }
    }

    /* Print: saved vocab list only */
    body.print-saved-mode .site-body,
    body.print-saved-mode footer { display: none !important; }
    body.print-saved-mode .saved-panel-overlay { display: block !important; position: static !important; background: none !important; }
    body.print-saved-mode .saved-panel { box-shadow: none; border: none; width: 100%; height: auto; }
    body.print-saved-mode .saved-panel-head { position: static; }
    body.print-saved-mode .saved-panel-actions { display: none; }
    @media print {
      body.print-saved-mode .topbar { display: none !important; }
    }

    /* ── RESPONSIVE ── */
    @media (max-width: 1024px) {
      .site-body { grid-template-columns: 180px 1fr; }
      .right-sidebar { display: none; }
    }
    @media (max-width: 720px) {
      .site-body { grid-template-columns: 1fr; }
      .left-sidebar { display: none; }
      .main-content { padding: 1rem; }
      .articles-grid { grid-template-columns: 1fr; }
      .hero-headline { font-size: 1.15rem; }
      .vocab-grid { grid-template-columns: 1fr; }
      .bw .tip { width: 190px; }
    }
    @media (max-width: 480px) {
      .topbar-nav { display: none; }
      .logo-name { font-size: 1rem; }
    }

    /* ── TRENDS MAIN FEED ── */
    .trends-grid { margin-top: 0.5rem; }
    .trend-main-item { padding: 1.25rem; }
    .trend-main-headline {
      font-family: 'DM Serif Display', serif; font-size: 1.05rem;
      color: var(--ink); margin: 0.5rem 0 0.75rem; line-height: 1.35;
    }

    /* ── FULL-SCREEN OVERLAY ── */
    .full-overlay {
      display: none; position: fixed; inset: 0; z-index: 9999;
      background: var(--bg); overflow-y: auto;
    }
    .full-overlay.open { display: block; }
    .full-overlay-inner {
      max-width: 860px; margin: 0 auto; padding: 2rem 1.5rem 4rem;
    }
    .full-overlay-topbar {
      display: flex; align-items: center; gap: 0.75rem;
      margin-bottom: 1.5rem;
    }
    .full-close-btn {
      background: none; border: 1px solid var(--border); border-radius: 6px;
      padding: 0.35rem 0.75rem; cursor: pointer; font-size: 0.85rem;
      color: var(--ink); display: flex; align-items: center; gap: 0.4rem;
    }
    .full-close-btn:hover { background: var(--faint); }
    .full-headline {
      font-family: 'DM Serif Display', serif; font-size: clamp(1.4rem,3vw,2rem);
      line-height: 1.25; color: var(--ink); margin: 0 0 0.5rem;
    }
    .full-meta {
      font-size: 0.82rem; color: var(--muted); margin-bottom: 1.5rem;
      display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    }
    .full-body { color: var(--sub); }
    .full-body .news-body,
    .full-body .trend-body { font-size: 1rem; line-height: 1.85; margin-bottom: 1.5rem; }
    .full-body .study-section,
    .full-body .study-drawer { display: block !important; }
    .full-body .study-toggle,
    .full-body .trend-study-toggle { display: none !important; }
    .full-body .vocab-grid { grid-template-columns: repeat(auto-fill, minmax(220px,1fr)); }
    /* clickable headline style */
    .clickable-headline {
      cursor: pointer; transition: color 0.15s;
    }
    .clickable-headline:hover { color: var(--accent); }

    /* ── GOOGLE AUTH ── */
    .auth-login-btn {
      display: flex; align-items: center; gap: 0.4rem;
      background: var(--accent); color: #fff; border: none;
      border-radius: 6px; padding: 0.35rem 0.85rem;
      cursor: pointer; font-size: 0.82rem; font-weight: 600;
      transition: opacity 0.15s; white-space: nowrap;
    }
    .auth-login-btn:hover { opacity: 0.88; }
    .auth-user-pill {
      display: none; align-items: center; gap: 0.4rem;
      background: var(--faint); border: 1px solid var(--border);
      border-radius: 20px; padding: 0.2rem 0.65rem 0.2rem 0.3rem;
      cursor: pointer; transition: background 0.15s;
    }
    .auth-user-pill:hover { background: var(--border); }
    .auth-avatar { width: 24px; height: 24px; border-radius: 50%; background: var(--ink); color: var(--surface);
                   display: inline-flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; }
    .auth-user-name { font-size: 0.78rem; color: var(--ink); max-width: 90px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    /* ── ARTICLE NOTES ── */
    .article-note-section { margin-top: 1.4rem; border-top: 1px solid var(--border); padding-top: 1rem; }
    .note-label { font-size: 0.78rem; font-weight: 700; color: var(--muted); letter-spacing: 0.05em; margin-bottom: 0.5rem; text-transform: uppercase; }
    .note-login-hint { font-size: 0.82rem; color: var(--muted); font-style: italic; }
    .note-login-hint button { background: none; border: none; color: var(--accent); cursor: pointer; font-size: inherit; text-decoration: underline; padding: 0; }
    .note-textarea {
      width: 100%; min-height: 80px; padding: 0.55rem 0.7rem;
      border: 1px solid var(--border); border-radius: 6px;
      background: var(--bg); color: var(--ink);
      font: 0.88rem/1.65 inherit; resize: vertical; box-sizing: border-box;
      display: none;
    }
    .note-textarea:focus { outline: none; border-color: var(--accent); }
    .note-save-row { display: none; align-items: center; gap: 0.6rem; margin-top: 0.4rem; }
    .note-save-btn {
      padding: 0.28rem 0.7rem; background: var(--accent); color: #fff;
      border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 600;
    }
    .note-save-btn:hover { opacity: 0.88; }
    .note-status { font-size: 0.77rem; color: var(--accent); }

    /* ── BILINGUAL ARTICLE (EN left / 中文 right) ── */
    .bi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1rem; }
    .bi-col { min-width: 0; }
    .bi-zh { border-left: 1px solid var(--border); padding-left: 1.5rem;
             font-family: 'Noto Sans HK', sans-serif; font-size: 0.95rem; line-height: 1.95; color: var(--sub); }
    .bi-zh p + p { margin-top: 0.8rem; }
    .bi-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
                color: var(--muted); margin-bottom: 0.5rem; }
    /* cards are previews: English only; the full view shows both columns */
    .article-card .bi-grid { display: block; }
    .article-card .bi-zh, .article-card .bi-label { display: none; }
    .full-body .bi-grid { display: grid; }
    .full-body .bi-zh, .full-body .bi-label { display: block; }
    @media (max-width: 760px) {
      .bi-grid, .full-body .bi-grid { grid-template-columns: 1fr; }
      .bi-zh { border-left: 0; padding-left: 0; border-top: 1px solid var(--border); padding-top: 1rem; }
    }

    /* ── COVERS ── */
    .hero-media, .card-thumb-wrap { position: relative; }
    .cover-fallback { position: absolute; inset: 0; display: flex; flex-direction: column;
                      align-items: center; justify-content: center; gap: 0.35rem; color: #fff; }
    .cover-emoji { font-size: 2.6rem; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.25)); }
    .cover-hero .cover-emoji { font-size: 4rem; }
    .cover-label { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.9; }
    .hero-img, .card-thumb { position: relative; z-index: 1; }
    .hero-overlay, .hero-overlay-text { z-index: 2; }
    .card-thumb-wrap { cursor: pointer; }

    /* ── LIBRARY ── */
    .library-intro { margin: 2.5rem 0 0.5rem; padding-top: 1.5rem; border-top: 2px solid var(--border); }
    .library-intro h2 { font-family: 'DM Serif Display', serif; font-size: 1.6rem; color: var(--ink); margin: 0 0 0.25rem; }
    .library-intro p { color: var(--muted); font-size: 0.88rem; margin: 0; }
    .library-section { margin-top: 1.5rem; }
    .full-overlay-inner { max-width: 1120px; }

    /* ══ REDESIGN — "MTR lines" identity ═════════════════════════════════
       Topics are MTR lines; vocabulary is marked like a highlighter pen.
       Everything below overrides the original theme. */
    :root {
      --bg: #F5F6F8; --surface: #FFFFFF; --border: #DFE2E8; --faint: #ECEEF2;
      --ink: #151922; --sub: #343B48; --muted: #687082;
      --accent: #D7261E; --accent-hover: #B01E17; --accent-light: #FBE9E8;
      --hl: #FFE45C; --hl-ink: #151922;
      --sidebar-active: #ECEEF2;
      --shadow-sm: 0 1px 2px rgba(21,25,34,0.06);
      --shadow-md: 0 6px 20px rgba(21,25,34,0.10);
      --f-ui: 'Archivo', 'Noto Sans HK', system-ui, sans-serif;
      --f-read: 'Source Serif 4', Georgia, 'Noto Serif HK', serif;
      --f-zh: 'Noto Serif HK', 'Noto Sans HK', 'PingFang HK', serif;
    }
    @media (prefers-color-scheme: dark) {
      :root:not([data-theme="light"]) {
        --bg: #0F1218; --surface: #171B23; --border: #2A303C; --faint: #1E232D;
        --ink: #EEF0F4; --sub: #C5CAD4; --muted: #8A92A3;
        --accent: #FF5A4F; --accent-hover: #FF7A71; --accent-light: #3A1A19;
        --hl: #8A7414; --hl-ink: #FFF8D6;
        --sidebar-active: #1E232D;
      }
    }
    :root[data-theme="dark"] {
      --bg: #0F1218; --surface: #171B23; --border: #2A303C; --faint: #1E232D;
      --ink: #EEF0F4; --sub: #C5CAD4; --muted: #8A92A3;
      --accent: #FF5A4F; --accent-hover: #FF7A71; --accent-light: #3A1A19;
      --hl: #8A7414; --hl-ink: #FFF8D6;
      --sidebar-active: #1E232D;
    }

    body { background: var(--bg); color: var(--ink); font-family: var(--f-ui); }
    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

    /* Top bar */
    .topbar { background: var(--surface); border-bottom: 1px solid var(--border); box-shadow: none; }
    .topbar-inner { max-width: 1320px; margin: 0 auto; gap: 1rem; }
    .logo { gap: 0.6rem; }
    .logo-mark { display: none; }
    .logo-name { font-family: var(--f-ui); font-stretch: 125%; font-weight: 800; font-size: 1.15rem;
                 letter-spacing: -0.01em; color: var(--ink); }
    .logo-zh { font-family: var(--f-zh); font-weight: 600; font-size: 0.95rem; color: var(--accent); }
    .topbar-right { margin-left: auto; gap: 0.6rem; }
    .topbar-date strong { font-weight: 500; color: var(--muted); font-size: 0.8rem; }
    .btn-open-saved, .btn-print-page {
      font-family: var(--f-ui); background: var(--surface); color: var(--ink);
      border: 1px solid var(--border); border-radius: 999px; padding: 0.38rem 0.85rem; font-weight: 600;
    }
    .btn-open-saved:hover, .btn-print-page:hover { border-color: var(--ink); }
    .auth-login-btn { background: var(--ink); color: var(--surface); border-radius: 999px; font-family: var(--f-ui); }
    .auth-login-btn svg path { fill: var(--surface); }

    /* Route strip — the one bold element */
    .route-strip {
      position: sticky; top: 0; z-index: 90; background: var(--surface);
      border-bottom: 1px solid var(--border);
    }
    .topbar { position: relative; }
    .route-inner {
      max-width: 1320px; margin: 0 auto; padding: 0.9rem 1.25rem 0.7rem;
      display: flex; overflow-x: auto; scrollbar-width: none; position: relative;
    }
    .route-inner::-webkit-scrollbar { display: none; }
    .line-stop {
      --line: #151922;
      flex: 0 0 auto; display: grid; grid-template-rows: auto auto; justify-items: center;
      gap: 0.35rem; padding: 0 0.85rem; background: none; border: 0; cursor: pointer;
      font-family: var(--f-ui); color: var(--sub); position: relative; min-width: 84px;
    }
    /* the track between stations */
    .line-stop::before {
      content: ""; position: absolute; top: 7px; left: 0; right: 0; height: 4px;
      background: var(--line); opacity: 0.9;
    }
    .line-stop:first-child::before { left: 50%; }
    .line-stop:last-child::before { right: 50%; }
    .stop-dot {
      width: 18px; height: 18px; border-radius: 50%; background: var(--surface);
      border: 4px solid var(--line); position: relative; z-index: 1; box-sizing: border-box;
      transition: transform 0.15s ease;
    }
    .stop-name { font-size: 0.78rem; font-weight: 600; white-space: nowrap; line-height: 1.1; }
    .stop-count { font-size: 0.68rem; color: var(--muted); font-variant-numeric: tabular-nums; margin-top: -0.2rem; }
    .line-stop:hover .stop-dot { transform: scale(1.15); }
    .line-stop.active .stop-dot { background: var(--line); }
    .line-stop.active .stop-name { color: var(--ink); }
    .line-stop.empty { opacity: 0.45; }

    /* Page grid: main + right rail (left sidebar removed) */
    .site-body { max-width: 1320px; margin: 0 auto; display: grid;
                 grid-template-columns: minmax(0, 1fr) 300px; gap: 2rem; padding: 1.5rem 1.25rem 3rem; }
    .main-content { padding: 0; min-width: 0; }
    .right-sidebar { position: sticky; top: 96px; align-self: start; }

    /* Section heads */
    .main-section-head { display: flex; align-items: baseline; justify-content: space-between;
                         gap: 1rem; margin: 2.2rem 0 1rem; border: 0; padding: 0; }
    .today-head { margin-top: 0.4rem; }
    .main-section-head h2, .library-intro h2 {
      font-family: var(--f-ui); font-stretch: 112%; font-weight: 800; font-size: 1.45rem;
      letter-spacing: -0.015em; color: var(--ink); margin: 0;
    }
    .section-see-all { font-size: 0.82rem; color: var(--muted); font-weight: 500; }
    .line-head { padding-left: 0.85rem; border-left: 6px solid var(--line); }
    .library-intro { border-top: 1px solid var(--border); margin-top: 3rem; padding-top: 2rem; }
    .library-intro p { font-size: 0.92rem; }

    /* Category chip = line badge */
    .cat-chip { --line: #151922; display: inline-flex; align-items: center; gap: 0.4rem;
                background: none !important; color: var(--sub) !important; padding: 0;
                font-family: var(--f-ui); font-size: 0.75rem; font-weight: 700; letter-spacing: 0.01em;
                text-transform: none; }
    .cat-chip::before { content: ""; width: 10px; height: 10px; border-radius: 50%;
                        border: 3px solid var(--line); background: var(--surface); }
    .hero-overlay-text .cat-chip { color: #fff !important; }
    .hero-overlay-text .cat-chip::before { background: transparent; }

    /* Hero */
    .hero-card { border-radius: 14px; border: 1px solid var(--border); background: var(--surface);
                 box-shadow: none; overflow: hidden; }
    .hero-card:hover { box-shadow: none; }
    .hero-media { aspect-ratio: 16 / 8; }
    .hero-overlay { background: linear-gradient(to top, rgba(10,12,18,0.92) 0%, rgba(10,12,18,0.45) 45%, rgba(10,12,18,0) 75%); }
    .hero-overlay-text { padding: 1.6rem 1.8rem; }
    .hero-headline { font-family: var(--f-ui); font-stretch: 112%; font-weight: 800;
                     font-size: clamp(1.5rem, 3.2vw, 2.4rem); line-height: 1.08; letter-spacing: -0.02em;
                     max-width: 26ch; text-wrap: balance; color: #fff; margin: 0.5rem 0 0.6rem; }
    .hero-source { color: #fff; text-decoration: underline; text-underline-offset: 3px; }
    .hero-body { padding: 1.6rem 1.8rem 1.4rem; }

    /* Reading text */
    .news-body, .card-summary, .trend-body {
      font-family: var(--f-read); font-size: 1.02rem; line-height: 1.78; color: var(--sub);
    }
    .news-body p, .trend-body p { max-width: 68ch; }
    .bi-zh { font-family: var(--f-zh); font-size: 1rem; line-height: 2; }
    .bi-label { font-family: var(--f-ui); letter-spacing: 0.02em; text-transform: none; font-size: 0.78rem;
                color: var(--muted); font-weight: 700; }

    /* Vocabulary = highlighter */
    .bw { color: var(--hl-ink); font-weight: 600; border-bottom: 0; cursor: help;
          background: linear-gradient(transparent 58%, var(--hl) 58%, var(--hl) 92%, transparent 92%);
          padding: 0 1px; }
    .bw .tip { font-family: var(--f-ui); }
    .bwz { color: var(--hl-ink); font-weight: 600; cursor: pointer;
           background: linear-gradient(transparent 55%, var(--hl) 55%, var(--hl) 95%, transparent 95%); }
    .bw[data-k], .bwz { transition: background-color 0.12s ease, box-shadow 0.12s ease; border-radius: 2px; }
    .bw.pair-on, .bwz.pair-on { background: var(--hl); box-shadow: 0 0 0 2px var(--accent); }
    .article-card .bwz { background: none; font-weight: inherit; }

    /* Cards */
    .articles-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 1.1rem; }
    .article-card { border-radius: 12px; border: 1px solid var(--border); background: var(--surface);
                    box-shadow: none; overflow: hidden; transition: border-color 0.15s ease; }
    .article-card:hover { transform: none; box-shadow: none; border-color: var(--ink); }
    .article-card:hover .card-thumb { transform: none; }
    .card-thumb-wrap { aspect-ratio: 16 / 10; }
    .card-body { padding: 0.95rem 1.05rem 1.1rem; gap: 0.5rem; }
    .card-headline { font-family: var(--f-ui); font-weight: 700; font-size: 1.04rem; line-height: 1.3;
                     letter-spacing: -0.005em; color: var(--ink); text-wrap: pretty; }
    .card-source { color: var(--ink); font-weight: 600; }
    .card-excerpt { font-size: 0.92rem; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 4;
                    -webkit-box-orient: vertical; overflow: hidden; margin: 0; }
    .read-more-btn { align-self: flex-start; margin-top: auto; background: none; border: 0; padding: 0.2rem 0;
                     font-family: var(--f-ui); font-weight: 700; font-size: 0.85rem; color: var(--accent);
                     cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
    .read-more-btn:hover { color: var(--accent-hover); }
    .loading .read-more-btn { opacity: 0.5; pointer-events: none; }
    /* trend cards are previews; the full view shows everything */
    .trends-grid .trend-main-item { display: flex; flex-direction: column; gap: 0.5rem; }
    .trends-grid .bi-grid { display: block; }
    .trends-grid .bi-zh, .trends-grid .bi-label, .trends-grid .causes-block { display: none; }
    .trends-grid .trend-body { display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical;
                               overflow: hidden; font-size: 0.95rem; line-height: 1.6; }
    .full-body .trend-body { display: block; -webkit-line-clamp: unset; }
    .full-body .bi-grid .bi-zh, .full-body .bi-label, .full-body .causes-block { display: block; }
    .full-body .bi-grid { display: grid; }
    .full-body + .read-more-btn, .full-body .read-more-btn { display: none; }
    .cover-label { text-transform: none; letter-spacing: 0.01em; font-family: var(--f-ui); font-size: 0.85rem; }

    /* Trends */
    .trend-main-item { border-radius: 12px; }
    .trend-main-headline { font-family: var(--f-ui); font-weight: 700; font-size: 1.08rem; }
    .causes-title { font-family: var(--f-ui); font-weight: 700; text-transform: none; letter-spacing: 0;
                    font-size: 0.9rem; color: var(--ink); }
    .causes-list li { line-height: 1.6; }
    .causes-list strong { color: var(--ink); }

    /* Study notes */
    .study-toggle { border-radius: 8px; border: 1px solid var(--border); background: var(--faint); }
    .study-toggle-label { font-family: var(--f-ui); color: var(--ink); font-size: 0.85rem; }
    .vocab-section-label { font-family: var(--f-ui); text-transform: none; letter-spacing: 0;
                           font-size: 0.95rem; font-weight: 700; color: var(--ink); }
    .note-label { text-transform: none; letter-spacing: 0; font-size: 0.9rem; color: var(--ink); }
    .note-save-btn { background: var(--ink); color: var(--surface); border-radius: 999px; padding: 0.35rem 0.9rem; }

    /* Right rail */
    .sidebar-widget-head h3 { font-family: var(--f-ui); font-weight: 800; font-size: 1rem; }
    .countdown-widget { border-radius: 12px; }
    .countdown-days { font-family: var(--f-ui); font-stretch: 125%; font-weight: 800; color: var(--accent); }

    /* Full-screen reading view */
    .full-overlay { background: var(--bg); }
    .full-overlay-inner { max-width: 1180px; padding: 1.5rem 1.5rem 5rem; }
    .full-headline { font-family: var(--f-ui); font-stretch: 112%; font-weight: 800; letter-spacing: -0.02em;
                     line-height: 1.1; max-width: 30ch; text-wrap: balance; }
    .full-body .bi-grid { gap: 2.5rem; background: var(--surface); border: 1px solid var(--border);
                          border-radius: 14px; padding: 1.8rem 2rem; }
    .full-body .bi-zh { padding-left: 2.5rem; }
    .full-close-btn { border-radius: 999px; font-family: var(--f-ui); font-weight: 600; }

    /* Portrait covers (4:5, Instagram-style, headline printed on the image) */
    .hero-top { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 0; }
    .hero-media { aspect-ratio: 4 / 5; cursor: pointer; background: var(--faint); }
    .hero-media .hero-img { width: 100%; height: 100%; object-fit: cover; }
    .hero-card:hover .hero-img { transform: none; }
    .hero-head { padding: 2rem 2rem 1.6rem; display: flex; flex-direction: column; gap: 0.7rem; }
    .hero-head .hero-headline { color: var(--ink); margin: 0.2rem 0 0; font-size: clamp(1.5rem, 2.6vw, 2.2rem); }
    .hero-head .hero-byline { color: var(--muted); }
    .hero-head .hero-source { color: var(--ink); }
    .hero-head .hero-dot { color: var(--border); }
    .hero-head .cat-chip { color: var(--sub) !important; }
    .hero-head .cat-chip::before { background: var(--surface); }
    .hero-excerpt { font-family: var(--f-read); font-size: 1.05rem; line-height: 1.7; color: var(--sub); margin: 0.4rem 0 0; }
    .hero-read { margin-top: auto; font-size: 1rem; }
    .hero-body { border-top: 1px solid var(--border); }
    .card-thumb-wrap { aspect-ratio: 4 / 5; }
    .hero-top.has-banner { grid-template-columns: 1fr; }
    .hero-top.has-banner .hero-media { aspect-ratio: 21 / 9; }
    .hero-top.has-banner .hero-head { padding-bottom: 1.4rem; }
    @media (max-width: 760px) {
      .hero-top { grid-template-columns: 1fr; }
      .hero-head { padding: 1.2rem; }
    }

    /* Article view sits below the sticky top bar + topic strip */
    .full-overlay { top: 150px; z-index: 80; }
    .full-overlay-inner { padding-top: 1rem; }

    /* Easier-to-read study notes */
    .vocab-phrase { font-size: 1.05rem; }
    .vocab-zh { font-size: 0.98rem; }
    .vocab-sample { font-size: 0.98rem; line-height: 1.6; }
    .phrase-table { font-size: 0.98rem; }
    .phrase-table td { padding: 0.6rem 0.8rem; }
    .phrase-table .zh-col { font-family: var(--f-zh); }
    .writing-angle-label { font-size: 1.05rem; }
    .writing-angle-text { font-size: 1rem; line-height: 1.7; }
    .note-textarea { font-size: 1rem; }

    /* DSE writing angles: larger, bilingual */
    .causes-block { margin-top: 1.4rem; }
    .causes-title { font-size: 1.15rem !important; margin-bottom: 0.6rem; }
    .causes-list { gap: 0.9rem; }
    .causes-list li.angle { padding-left: 0; }
    .causes-list li.angle::before { content: none; }
    .angle { border-left: 4px solid var(--accent); padding: 0.2rem 0 0.2rem 0.9rem !important; }
    .angle-head { display: flex; align-items: center; flex-wrap: wrap; gap: 0.45rem; font-size: 1.08rem; color: var(--ink); }
    .angle-zh-label { font-family: var(--f-zh); font-weight: 600; color: var(--sub); font-size: 1rem; }
    .angle-text { font-family: var(--f-read); font-size: 1.05rem; line-height: 1.7; color: var(--sub); margin-top: 0.25rem; }
    .angle-zh { font-family: var(--f-zh); font-size: 1rem; line-height: 1.85; color: var(--muted); margin-top: 0.3rem; }
    .trend-body { font-size: 1.02rem; }

    /* trend cards stay short previews; everything shows in the article view */
    .trends-grid .study-toggle, .trends-grid .study-drawer, .trends-grid .article-actions { display: none; }
    .full-body .study-drawer { display: block !important; }

    /* Print + share bar at the bottom of each article */
    .article-actions { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: 1.4rem;
                       padding-top: 1.1rem; border-top: 1px solid var(--border); }
    .act-btn { font-family: var(--f-ui); font-weight: 600; font-size: 0.88rem; cursor: pointer;
               background: var(--surface); color: var(--ink); border: 1px solid var(--border);
               border-radius: 999px; padding: 0.5rem 1rem; }
    .act-btn:hover { border-color: var(--ink); }
    .act-share { background: var(--ink); color: var(--surface); border-color: var(--ink); }
    .act-share:hover { opacity: 0.88; }
    .card-excerpt { cursor: pointer; }

    /* Share menu */
    .share-sheet { position: fixed; inset: 0; z-index: 10001; background: rgba(10, 12, 18, 0.55);
                   display: flex; align-items: flex-end; justify-content: center; padding: 1rem; }
    .share-sheet[hidden] { display: none !important; }
    .share-box { background: var(--surface); color: var(--ink); width: 100%; max-width: 460px;
                 border-radius: 16px; padding: 1.3rem 1.3rem 1rem; box-shadow: var(--shadow-md);
                 margin-bottom: max(1rem, env(safe-area-inset-bottom)); }
    @media (min-width: 700px) { .share-sheet { align-items: center; } }
    .share-label { font-family: var(--f-ui); font-size: 0.8rem; color: var(--muted); font-weight: 600; }
    .share-head { font-family: var(--f-ui); font-weight: 700; font-size: 1.02rem; line-height: 1.3;
                  margin: 0.25rem 0 1rem; text-wrap: balance; }
    .share-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 0.5rem; }
    .share-opt { font-family: var(--f-ui); font-weight: 600; font-size: 0.9rem; text-align: center;
                 text-decoration: none; color: var(--ink); background: var(--faint); border: 1px solid var(--border);
                 border-radius: 10px; padding: 0.7rem 0.5rem; cursor: pointer; }
    .share-opt:hover { border-color: var(--ink); }
    .share-native { grid-column: 1 / -1; background: var(--ink); color: var(--surface); border-color: var(--ink); }
    .share-status { min-height: 1.3em; font-size: 0.85rem; color: var(--accent); margin-top: 0.7rem; }
    .share-close { width: 100%; margin-top: 0.4rem; font-family: var(--f-ui); font-weight: 600; cursor: pointer;
                   background: none; border: 1px solid var(--border); border-radius: 999px; padding: 0.55rem;
                   color: var(--ink); }

    /* Mobile */
    @media (max-width: 1080px) {
      .site-body { grid-template-columns: 1fr; }
      .right-sidebar { position: static; }
    }
    @media (max-width: 640px) {
      .topbar-date { display: none; }
      .auth-user-name { display: none; }
      .hero-body { padding: 1.2rem; }
      .full-body .bi-grid { padding: 1.2rem; gap: 1.2rem; }
      .full-body .bi-zh { padding-left: 0; }
      .line-stop { min-width: 72px; padding: 0 0.55rem; }
    }
    @media (prefers-reduced-motion: reduce) {
      * { transition: none !important; scroll-behavior: auto !important; }
    }

    /* ══ MAGAZINE + APP LAYOUT ══════════════════════════════════════════════ */
    :root {
      --f-ui: 'Titillium Web', 'Noto Sans HK', system-ui, sans-serif;
      --accent: #157A5B; --accent-hover: #0F5E45; --accent-light: #E3F2EC;
      --bg: #F4F5F7; --radius: 16px;
    }
    @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --accent: #4FC79C; --accent-hover: #7DDBB8; --accent-light: #12352A; } }
    :root[data-theme="dark"] { --accent: #4FC79C; --accent-hover: #7DDBB8; --accent-light: #12352A; }
    html { -webkit-text-size-adjust: 100%; }
    body { font-family: var(--f-ui); }

    /* header: dark bar + topic pills */
    .site-header { position: sticky; top: 0; z-index: 90; }
    .route-strip { display: none !important; }
    .topbar { background: #111418; border-bottom: 0; }
    .topbar .logo-name { color: #fff; font-family: var(--f-ui); font-stretch: normal; font-weight: 700; font-size: 1.3rem; letter-spacing: -0.01em; }
    .topbar .logo-zh { color: #FFD43B; font-family: var(--f-zh); }
    .topbar .topbar-date strong { color: #A9B0BC; }
    .topbar .btn-open-saved { background: transparent; color: #fff; border-color: #3A404B; }
    .topbar .auth-login-btn { background: #fff; color: #111418; }
    .topbar .auth-login-btn svg path { fill: #111418; }
    .topbar .auth-user-pill { background: #22272F; border-color: #3A404B; }
    .topbar .auth-user-name { color: #fff; }
    .topic-nav { background: #111418; border-top: 1px solid #22272F; }
    .topic-inner { max-width: 1240px; margin: 0 auto; display: flex; gap: 0.4rem; overflow-x: auto;
                   padding: 0.55rem 1.25rem 0.7rem; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
    .topic-inner::-webkit-scrollbar { display: none; }
    .topic-nav .line-stop { flex: 0 0 auto; display: inline-block; min-width: 0; padding: 0.42rem 0.95rem; border-radius: 999px;
                            border: 1px solid #3A404B; background: transparent; color: #D6DAE1; font-family: var(--f-ui);
                            font-weight: 600; font-size: 0.92rem; cursor: pointer; white-space: nowrap; }
    .topic-nav .line-stop::before { content: none; }
    .topic-nav .line-stop:hover { border-color: #fff; color: #fff; }
    .topic-nav .line-stop.active { background: var(--accent); border-color: var(--accent); color: #fff; }

    /* news update ticker */
    .news-update { display: flex; align-items: center; gap: 0.9rem; max-width: 1240px; margin: 1rem auto 0;
                   padding: 0.55rem 1rem; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
    .nu-label { flex: 0 0 auto; color: #D7261E; font-weight: 700; font-size: 0.92rem; }
    .tick-track { display: flex; overflow: hidden; flex: 1; min-width: 0; -webkit-mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent); }
    .tick-run { display: flex; flex: 0 0 auto; gap: 2rem; padding-right: 2rem; animation: tick 70s linear infinite; }
    .news-update:hover .tick-run { animation-play-state: paused; }
    .tick-item { background: none; border: 0; padding: 0; font: 500 0.92rem var(--f-ui); color: var(--ink); white-space: nowrap; cursor: pointer; }
    .tick-item::before { content: "●"; color: #D7261E; font-size: 0.55rem; margin-right: 0.6rem; vertical-align: middle; }
    @keyframes tick { from { transform: translateX(0); } to { transform: translateX(-100%); } }

    /* page */
    .mag { max-width: 1240px; margin: 0 auto; padding: 1.2rem 1.25rem 3rem; }
    .mag-section { margin-top: 2.4rem; }
    .mag-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
    .mag-h2 { --line: var(--accent); font-family: var(--f-ui); font-weight: 700; font-size: 1.45rem; color: var(--ink);
              margin: 0; padding-left: 0.7rem; border-left: 4px solid var(--line); line-height: 1.15; }
    .mag-dot { width: 3px; height: 3px; border-radius: 50%; background: currentColor; opacity: 0.5; display: inline-block; }
    .mag-pill { --line: #151922; display: inline-block; font: 600 0.78rem var(--f-ui); color: #fff; background: var(--line);
                padding: 0.25rem 0.7rem; border-radius: 999px; line-height: 1.3; }
    .mag-pill-glass { background: rgba(255,255,255,0.18); backdrop-filter: blur(6px); border: 1px solid rgba(255,255,255,0.35); }
    .mag-meta { display: flex; align-items: center; gap: 0.45rem; font-size: 0.86rem; color: var(--muted); }
    .mag-src { font-weight: 600; color: var(--ink); }
    .mag-excerpt { font-size: 0.98rem; line-height: 1.6; color: var(--sub); margin: 0; cursor: pointer;
                   display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
    .cover-mag { position: absolute; inset: 0; display: block; color: #fff; }
    .cover-mag .cover-label { display: none; }
    .cover-mag .cover-emoji { position: absolute; top: 14%; right: 9%; font-size: clamp(2.4rem, 9vw, 4.2rem); opacity: 0.9; }
    .mag-list-thumb .cover-mag .cover-emoji, .mag-card-media .cover-mag .cover-emoji { top: 50%; left: 50%; right: auto;
      transform: translate(-50%, -50%); font-size: 2.6rem; }

    /* hero */
    .mag-hero { position: relative; border-radius: 20px; overflow: hidden; background: #1b1f26; min-height: 520px; display: flex; flex-direction: column; justify-content: flex-end; }
    .mag-hero-media { position: absolute; inset: 0; cursor: pointer; }
    .mag-hero-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1; }
    .mag-hero-shade { position: absolute; inset: 0; z-index: 2; pointer-events: none;
                      background: linear-gradient(90deg, rgba(8,10,14,0.85) 0%, rgba(8,10,14,0.55) 45%, rgba(8,10,14,0.1) 80%),
                                  linear-gradient(0deg, rgba(8,10,14,0.7) 0%, rgba(8,10,14,0) 45%); }
    .mag-hero-text { position: relative; z-index: 3; padding: 2.4rem 2.6rem 1.6rem; max-width: 760px; color: #fff; }
    .mag-hero-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    .mag-hero-title { font-family: var(--f-ui); font-weight: 700; color: #fff; font-size: clamp(1.9rem, 4.2vw, 3.3rem);
                      line-height: 1.08; letter-spacing: -0.01em; margin: 0.9rem 0 1.1rem; text-wrap: balance; cursor: pointer; }
    .mag-hero-read { display: flex; align-items: center; gap: 0.6rem; font-size: 0.95rem; }
    .mag-read-btn { width: 42px; height: 42px; border-radius: 50%; border: 1.5px solid rgba(255,255,255,0.7); background: transparent;
                    color: #fff; font-size: 1.1rem; cursor: pointer; }
    .mag-read-btn:hover { background: #fff; color: #111; }
    .mag-meta-hero { color: rgba(255,255,255,0.8); margin-top: 0.8rem; }
    .mag-meta-hero .mag-src { color: #fff; }
    .mag-hero-strip { position: relative; z-index: 3; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.7rem;
                      padding: 1rem 2.6rem 1.6rem; border-top: 1px solid rgba(255,255,255,0.15); background: rgba(8,10,14,0.35); }
    .hero-next { display: flex; align-items: center; gap: 0.7rem; text-align: left; background: rgba(255,255,255,0.1);
                 border: 1px solid rgba(255,255,255,0.18); border-radius: 12px; padding: 0.6rem 0.8rem; color: #fff;
                 font: 600 0.88rem/1.3 var(--f-ui); cursor: pointer; backdrop-filter: blur(6px); }
    .hero-next:hover { background: rgba(255,255,255,0.2); }
    .hero-next span:last-child { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .hero-next-num { flex: 0 0 auto; width: 30px; height: 30px; border-radius: 50%; border: 1.5px solid rgba(255,255,255,0.6);
                     display: grid; place-items: center; font-size: 0.85rem; }

    /* featured rail */
    .mag-arrows { display: flex; gap: 0.4rem; }
    .mag-arrow { width: 38px; height: 38px; border-radius: 50%; border: 1px solid var(--border); background: var(--surface);
                 color: var(--ink); cursor: pointer; font-size: 1rem; }
    .mag-arrow:hover { border-color: var(--ink); }
    .mag-rail { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(220px, 1fr); gap: 1rem;
                overflow-x: auto; scroll-snap-type: x mandatory; padding-bottom: 0.4rem; scrollbar-width: none; }
    .mag-rail::-webkit-scrollbar { display: none; }
    @media (min-width: 1100px) { .mag-rail { grid-auto-columns: calc((100% - 4rem) / 5); } }
    .mag-feature { position: relative; aspect-ratio: 4 / 5.4; border-radius: var(--radius); overflow: hidden; scroll-snap-align: start;
                   cursor: pointer; background: #1b1f26; }
    .mag-feature-media { position: absolute; inset: 0; }
    .mag-feature-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1; transition: transform 0.4s ease; }
    .mag-feature:hover .mag-feature-img { transform: scale(1.04); }
    .mag-feature-shade { position: absolute; inset: 0; z-index: 2; background: linear-gradient(0deg, rgba(8,10,14,0.9) 0%, rgba(8,10,14,0.25) 55%, rgba(8,10,14,0) 75%); }
    .mag-feature > .mag-pill { position: absolute; top: 0.8rem; left: 0.8rem; z-index: 3; }
    .mag-feature-text { position: absolute; left: 0; right: 0; bottom: 0; z-index: 3; padding: 1rem; }
    .mag-feature-title { color: #fff; font: 700 1.08rem/1.25 var(--f-ui); margin: 0 0 0.45rem; text-wrap: pretty; }
    .mag-meta-light { color: rgba(255,255,255,0.75); font-size: 0.8rem; }
    .mag-meta-light .mag-src { color: #fff; }

    /* latest + trending */
    .mag-split { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 2rem; align-items: start; }
    .mag-split.topic-view { grid-template-columns: 1fr; }
    .mag-list-item { display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: 1.1rem; padding: 1rem 0; border-bottom: 1px solid var(--border); }
    .mag-list-thumb { position: relative; aspect-ratio: 4 / 4.2; border-radius: 12px; overflow: hidden; cursor: pointer; background: var(--faint); }
    .mag-list-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; z-index: 1; }
    .mag-list-text { display: flex; flex-direction: column; gap: 0.45rem; min-width: 0; }
    .mag-list-title { font: 700 1.15rem/1.3 var(--f-ui); color: var(--ink); margin: 0; cursor: pointer; }
    .mag-list-foot { display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; font-size: 0.84rem; color: var(--muted); margin-top: auto; }
    .mag-side { position: sticky; top: 140px; display: flex; flex-direction: column; gap: 1.2rem; margin-top: 2.4rem; }
    .trending-box { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 1.2rem 1.2rem 0.6rem; }
    .trending-h { border-left-color: #F38B00; margin-bottom: 0.6rem; }
    .trend-row { display: flex; gap: 0.8rem; width: 100%; text-align: left; background: none; border: 0; border-top: 1px solid var(--border);
                 padding: 0.85rem 0; cursor: pointer; font-family: var(--f-ui); color: var(--ink); }
    .trend-row:first-of-type { border-top: 0; }
    .trend-num { font-weight: 700; font-size: 1.5rem; color: var(--border); line-height: 1; min-width: 2.2rem; }
    .trend-row:hover .trend-num { color: #F38B00; }
    .trend-row-text { display: flex; flex-direction: column; gap: 0.3rem; }
    .trend-row-title { font-weight: 600; font-size: 1rem; line-height: 1.35; }
    .trend-row-meta { display: flex; align-items: center; gap: 0.4rem; font-size: 0.8rem; color: var(--muted); }

    /* topic grids */
    .mag-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.6rem 1.4rem; }
    .mag-card { display: flex; flex-direction: column; gap: 0.55rem; }
    .mag-card-media { position: relative; aspect-ratio: 4 / 3.3; border-radius: 14px; overflow: hidden; cursor: pointer; background: var(--faint); }
    .mag-card-img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center 30%; z-index: 1; transition: transform 0.4s ease; }
    .mag-card:hover .mag-card-img { transform: scale(1.03); }
    .mag-card-title { font: 700 1.2rem/1.3 var(--f-ui); color: var(--ink); margin: 0; cursor: pointer; text-wrap: pretty; }
    .mag-card-foot { display: flex; align-items: center; gap: 0.45rem; font-size: 0.85rem; color: var(--muted); }
    .mag-cat-text { --line: var(--accent); color: var(--line); font-weight: 600; }
    .mag-trends .main-section-head { margin: 0 0 1rem; }
    .mag-trends .main-section-head h2 { font-family: var(--f-ui); font-weight: 700; font-size: 1.45rem; padding-left: 0.7rem; border-left: 4px solid #F38B00; }

    /* footer */
    .mag-footer { background: #111418; color: #A9B0BC; margin-top: 3rem; padding: 2.4rem 1.25rem 6rem; }
    .mag-footer-inner { max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: 1.4fr 1fr; gap: 2rem; }
    .mag-footer-brand { color: #fff; font-weight: 700; font-size: 1.3rem; }
    .mag-footer-brand span { color: #FFD43B; font-family: var(--f-zh); }
    .mag-footer p { max-width: 46ch; line-height: 1.6; }
    .mag-footer-tips { display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.92rem; }
    .mag-footer-tips b { color: #fff; }
    .mag-footer-small { max-width: 1240px; margin: 1.6rem auto 0; font-size: 0.8rem; border-top: 1px solid #22272F; padding-top: 1rem; }

    /* article view */
    .full-cover { position: relative; margin: 0 0 1.2rem; border-radius: var(--radius); overflow: hidden; max-height: 460px; }
    .full-cover img { display: block; width: 100%; height: 100%; max-height: 460px; object-fit: cover; }
    .full-cover:empty { display: none; }
    .lang-switch { display: inline-flex; background: var(--faint); border: 1px solid var(--border); border-radius: 999px; padding: 3px; margin: 0 0 1rem; }
    .lang-switch button { font: 600 0.92rem var(--f-ui); border: 0; background: transparent; color: var(--sub); padding: 0.4rem 0.95rem; border-radius: 999px; cursor: pointer; }
    .lang-switch button.on { background: var(--surface); color: var(--ink); box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
    .full-body.lang-en .bi-zh, .full-body.lang-zh .bi-en { display: none !important; }
    .full-body.lang-en .bi-grid, .full-body.lang-zh .bi-grid { grid-template-columns: 1fr !important; }
    .full-body.lang-zh .bi-zh { border: 0 !important; padding: 0 !important; }
    .full-body .news-body, .full-body .trend-body, .full-body .bi-en { font-size: 1.12rem; line-height: 1.8; }
    .full-body .bi-zh { font-size: 1.08rem; line-height: 2; }

    /* bottom tab bar (phones) */
    .tabbar { display: none; }

    /* ── PHONES & SMALL TABLETS ───────────────────────────────────────────── */
    @media (max-width: 900px) {
      .mag-split { grid-template-columns: 1fr; }
      .mag-side { position: static; margin-top: 1.6rem; }
      .mag-footer-inner { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
      body { font-size: 17px; }
      .topbar-inner { padding: 0.55rem 1rem; }
      .topbar-right .btn-open-saved, .topbar-right .auth-login-btn, .topbar-right .auth-user-pill, .topbar-date { display: none !important; }
      .topbar .logo-name { font-size: 1.2rem; }
      .topic-inner { padding: 0.45rem 1rem 0.6rem; }
      .topic-nav .line-stop { font-size: 0.95rem; padding: 0.45rem 1rem; }
      .news-update { margin: 0.8rem 1rem 0; }
      .mag { padding: 0.9rem 1rem 2rem; }
      .mag-section { margin-top: 1.8rem; }
      .mag-h2 { font-size: 1.3rem; }

      .mag-hero { min-height: 0; border-radius: 18px; }
      .mag-hero-media { position: relative; inset: auto; aspect-ratio: 4 / 4.6; }
      .mag-hero-shade { background: linear-gradient(0deg, rgba(8,10,14,0.92) 0%, rgba(8,10,14,0.5) 40%, rgba(8,10,14,0) 62%); }
      .mag-hero-text { position: absolute; left: 0; right: 0; bottom: 0; padding: 1.1rem 1.1rem 1rem; }
      .mag-hero-title { font-size: clamp(1.5rem, 7vw, 2rem); margin: 0.6rem 0 0.7rem; }
      .mag-hero-read { font-size: 0.9rem; }
      .mag-read-btn { width: 36px; height: 36px; }
      .mag-meta-hero { display: none; }
      .mag-hero-strip { display: none; }

      .mag-arrows { display: none; }
      .mag-rail { grid-auto-columns: 76%; gap: 0.8rem; margin: 0 -1rem; padding: 0 1rem 0.3rem; scroll-padding: 0 1rem; }
      .mag-feature-title { font-size: 1.12rem; }

      .mag-list-item { grid-template-columns: 112px minmax(0, 1fr); gap: 0.85rem; padding: 0.85rem 0; }
      .mag-list-thumb { aspect-ratio: 1 / 1.05; }
      .mag-list-title { font-size: 1.05rem; }
      .mag-list-item .mag-excerpt { display: none; }

      .mag-grid { grid-template-columns: 1fr; gap: 1.4rem; }
      .mag-card-title { font-size: 1.15rem; }

      /* article view: cover on top, text on a rounded sheet, large type */
      .full-overlay { top: 0 !important; z-index: 95; }
      .full-overlay-inner { padding: 0 0 7rem !important; }
      .full-overlay-topbar { position: sticky; top: 0; z-index: 3; padding: 0.6rem 1rem; margin: 0;
                             background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(10px); }
      .full-close-btn { font-size: 1rem; padding: 0.45rem 0.9rem; }
      .full-cover { border-radius: 0; margin: 0; max-height: none; }
      .full-cover img { max-height: 62vh; }
      .full-headline { font-size: 1.6rem !important; padding: 1.1rem 1.1rem 0; margin: -1.2rem 0 0; position: relative;
                       background: var(--bg); border-radius: 22px 22px 0 0; }
      .full-meta { padding: 0 1.1rem; }
      .lang-switch { margin: 0 1.1rem 0.9rem; }
      .full-body { padding: 0 1.1rem; }
      .full-body .bi-grid { display: block !important; padding: 0 !important; border: 0 !important; background: none !important; }
      .full-body .bi-zh { padding: 1rem 0 0 !important; margin-top: 1rem; border-left: 0 !important; border-top: 1px solid var(--border) !important; }
      .full-body .news-body, .full-body .trend-body, .full-body .bi-en { font-size: 1.15rem; line-height: 1.8; }
      .full-body .bi-zh { font-size: 1.12rem; line-height: 2; }
      .bw .tip { width: min(260px, 80vw); }

      /* study notes: stacked, larger */
      .vocab-grid { grid-template-columns: 1fr !important; }
      .vocab-phrase { font-size: 1.12rem; }
      .vocab-zh, .vocab-sample { font-size: 1.02rem; }
      .phrase-table thead { display: none; }
      .phrase-table, .phrase-table tbody, .phrase-table tr, .phrase-table td { display: block; width: 100%; }
      .phrase-table tr { border: 1px solid var(--border); border-radius: 12px; padding: 0.7rem 0.85rem; margin-bottom: 0.7rem; background: var(--surface); }
      .phrase-table td { border: 0 !important; padding: 0.15rem 0 !important; font-size: 1.02rem; background: none !important; }
      .phrase-table .en-col { font-weight: 700; }
      .angle-head { font-size: 1.1rem; }
      .angle-text { font-size: 1.08rem; }
      .angle-zh { font-size: 1.04rem; }
      .article-actions { display: grid; grid-template-columns: 1fr 1fr 1fr; }
      .act-btn { padding: 0.75rem 0.4rem; font-size: 0.95rem; text-align: center; }
      .speak-btn, .save-vocab-btn { min-width: 36px; min-height: 36px; }
      .note-textarea { font-size: 16px; }   /* 16px+ stops iPhone zooming the page */

      /* app-style bottom tab bar */
      .tabbar { display: grid; grid-template-columns: repeat(4, 1fr); position: fixed; left: 0.7rem; right: 0.7rem;
                bottom: calc(0.6rem + env(safe-area-inset-bottom)); z-index: 120; background: var(--surface);
                border: 1px solid var(--border); border-radius: 22px; box-shadow: 0 8px 28px rgba(0,0,0,0.16); padding: 0.35rem; }
      .tab { display: flex; flex-direction: column; align-items: center; gap: 0.1rem; border: 0; background: none; color: var(--muted);
             font: 600 0.72rem var(--f-ui); padding: 0.35rem 0; border-radius: 16px; cursor: pointer; }
      .tab-ico { font-size: 1.2rem; line-height: 1.2; }
      .tab.on { background: var(--accent); color: #fff; }
      .mag-footer { padding-bottom: 7rem; }
      .saved-panel { width: 100% !important; }
    }
    @media (max-width: 360px) {
      .mag-hero-title { font-size: 1.4rem; }
      .mag-list-item { grid-template-columns: 92px minmax(0, 1fr); }
      .article-actions { grid-template-columns: 1fr 1fr; }
    }
    @media (prefers-reduced-motion: reduce) { .tick-run { animation: none; } .mag-feature-img, .mag-card-img { transition: none; } }
"""

# ── JS ────────────────────────────────────────────────────────────────────────

JS = """
  // Header date
  (function() {
    var el = document.getElementById('today-date');
    if (el) el.textContent = new Date().toLocaleDateString('en-HK', {
      weekday:'long', year:'numeric', month:'long', day:'numeric',
      timeZone:'Asia/Hong_Kong'
    });
  })();

  // Sidebar & tab filter
  function filterCards(cat, el) {
    if (typeof closeFull === 'function') closeFull();
    document.querySelectorAll('.line-stop[data-cat]').forEach(function(b) {
      b.classList.toggle('active', b.dataset.cat === cat);
    });
    var home = cat === 'all';
    document.querySelectorAll('.home-only').forEach(function(x) { x.style.display = home ? '' : 'none'; });
    document.querySelectorAll('[data-cat]').forEach(function(c) {
      if (c.classList.contains('line-stop')) return;
      c.style.display = (home || c.dataset.cat.split(' ').indexOf(cat) !== -1) ? '' : 'none';
    });
    document.querySelectorAll('.mag-section').forEach(function(sec) {
      if (home) { sec.style.display = ''; return; }
      var any = Array.prototype.some.call(sec.querySelectorAll('[data-cat]'), function(c) { return c.style.display !== 'none'; });
      sec.style.display = any ? '' : 'none';
    });
    document.querySelectorAll('.mag-split').forEach(function(x) {
      x.classList.toggle('topic-view', !home);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  var _lang = 'both';
  try { _lang = localStorage.getItem('hkdse_lang') || (window.innerWidth < 640 ? 'en' : 'both'); } catch (e) {}
  function setLang(lang, btn) {
    _lang = lang;
    try { localStorage.setItem('hkdse_lang', lang); } catch (e) {}
    var body = document.getElementById('full-body');
    if (body) { body.classList.remove('lang-both', 'lang-en', 'lang-zh'); body.classList.add('lang-' + lang); }
    document.querySelectorAll('.lang-switch button').forEach(function(b) { b.classList.toggle('on', b.dataset.lang === lang); });
  }

  function tabTo(where, btn) {
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.toggle('on', t === btn); });
    if (where === 'home') { filterCards('all'); }
    else if (where === 'topics') { closeFull(); window.scrollTo({ top: 0, behavior: 'smooth' });
      var nav = document.querySelector('.topic-inner'); if (nav) { nav.scrollLeft = 0; nav.classList.add('pulse'); setTimeout(function(){ nav.classList.remove('pulse'); }, 900); } }
    else if (where === 'vocab') { toggleSavedPanel(); setTimeout(function(){ document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('on', t.id === 'tab-home'); }); }, 400); }
    else if (where === 'me') {
      if (window._fb && window._fb.auth.currentUser) signOutGoogle(); else signInWithGoogle();
      setTimeout(function(){ document.querySelectorAll('.tab').forEach(function(t){ t.classList.toggle('on', t.id === 'tab-home'); }); }, 400);
    }
  }

  function scrollRail(dir) {
    var r = document.getElementById('mag-rail');
    if (r) r.scrollBy({ left: dir * r.clientWidth * 0.8, behavior: 'smooth' });
  }

  // Study notes accordion
  function toggleStudy(uid) {
    var drawer = document.getElementById('drawer-' + uid);
    var icon   = document.getElementById('icon-' + uid);
    if (!drawer) return;
    var open = drawer.classList.toggle('open');
    if (icon) icon.classList.toggle('open', open);
  }

  // Text-to-speech
  function speak(text) {
    if (!window.speechSynthesis) { alert('Your browser does not support text-to-speech.'); return; }
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'en-GB'; u.rate = 0.82; u.pitch = 1.0;
    window.speechSynthesis.speak(u);
  }

  // ── SAVED VOCAB (localStorage, no account needed) ─────────────────────────
  var STORAGE_KEY = 'hkdse_saved_vocab';

  function _loadSaved() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
    catch(e) { return []; }
  }
  function _saveSaved(list) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch(e) {}
  }
  function _updateBadge() {
    var list = _loadSaved();
    var badge = document.getElementById('saved-count-badge');
    if (badge) badge.textContent = list.length > 0 ? list.length : '';
  }

  function saveVocab(phrase, zh, sample, btn) {
    var list = _loadSaved();
    var already = list.some(function(x){ return x.phrase === phrase; });
    if (already) {
      // Toggle off — remove it
      list = list.filter(function(x){ return x.phrase !== phrase; });
      _saveSaved(list);
      _updateBadge();
      if (btn) { btn.classList.remove('saved'); btn.title = 'Save to My List'; }
      renderSavedPanel();
      return;
    }
    list.push({ phrase: phrase, zh: zh, sample: sample, saved: Date.now() });
    _saveSaved(list);
    _updateBadge();
    if (btn) { btn.classList.add('saved'); btn.title = 'Saved! Click to remove'; }
    renderSavedPanel();
  }

  function removeSaved(phrase) {
    var list = _loadSaved().filter(function(x){ return x.phrase !== phrase; });
    _saveSaved(list);
    _updateBadge();
    renderSavedPanel();
    // un-highlight any matching save buttons on page
    document.querySelectorAll('.save-vocab-btn, .save-vocab-btn-sm').forEach(function(b) {
      var onclick = b.getAttribute('onclick') || '';
      if (onclick.indexOf(phrase.replace(/'/g,"\\'")) !== -1) {
        b.classList.remove('saved'); b.title = 'Save to My List';
      }
    });
  }

  function clearSaved() {
    if (!confirm('Clear your entire saved vocab list?')) return;
    _saveSaved([]);
    _updateBadge();
    renderSavedPanel();
    document.querySelectorAll('.save-vocab-btn, .save-vocab-btn-sm').forEach(function(b){
      b.classList.remove('saved'); b.title = 'Save to My List';
    });
  }

  function renderSavedPanel() {
    var list = _loadSaved();
    var body = document.getElementById('saved-panel-body');
    if (!body) return;
    if (list.length === 0) {
      body.innerHTML = '<div class="saved-empty">💡 Tap 💾 on any vocab or phrase to save it here for revision.<br><br>Your saved list is stored in this browser — no account needed.</div>';
      return;
    }
    body.innerHTML = list.map(function(item) {
      var ph = item.phrase.replace(/</g,'&lt;').replace(/>/g,'&gt;');
      var zh = item.zh.replace(/</g,'&lt;').replace(/>/g,'&gt;');
      var sm = item.sample.replace(/</g,'&lt;').replace(/>/g,'&gt;');
      var phEsc = item.phrase.replace(/'/g,"\\'");
      return '<div class="saved-vocab-item">' +
        '<button class="saved-vocab-remove" onclick="removeSaved(\\'' + phEsc + '\\')" title="Remove">✕</button>' +
        '<div class="saved-vocab-phrase">' + ph +
          ' <button class="speak-btn" onclick="speak(\\'' + phEsc + '\\')">🔊</button></div>' +
        '<div class="saved-vocab-zh">' + zh + '</div>' +
        (sm ? '<div class="saved-vocab-sample">\\"' + sm + '\\"</div>' : '') +
        '</div>';
    }).join('');
  }

  function toggleSavedPanel() {
    var overlay = document.getElementById('saved-panel-overlay');
    if (!overlay) return;
    overlay.classList.toggle('open');
    if (overlay.classList.contains('open')) renderSavedPanel();
  }

  // ── PRINT / SAVE AS PDF ───────────────────────────────────────────────────
  // Builds a clean, separate print page (works in Chrome, Safari, Edge, phones),
  // instead of printing the whole website.
  var PRINT_CSS = [
    '@page { size: A4; margin: 16mm 14mm; }',
    'body { font-family: "Source Serif 4", Georgia, "Noto Serif HK", serif; color: #111; margin: 0; font-size: 11.5pt; line-height: 1.6; }',
    'h1 { font-family: Archivo, Arial, sans-serif; font-size: 20pt; line-height: 1.15; margin: 0 0 4pt; }',
    '.brand { font-family: Archivo, Arial, sans-serif; font-size: 9pt; color: #555; border-bottom: 2px solid #111; padding-bottom: 4pt; margin-bottom: 10pt; display: flex; justify-content: space-between; }',
    '.meta { font-family: Archivo, Arial, sans-serif; font-size: 9.5pt; color: #555; margin: 0 0 12pt; }',
    'table.bi { width: 100%; border-collapse: collapse; table-layout: fixed; }',
    'table.bi td { vertical-align: top; padding: 0 8pt; }',
    'table.bi td.en { border-right: 1px solid #bbb; padding-left: 0; }',
    'table.bi td.zh { font-family: "Noto Serif HK", "Noto Sans HK", serif; font-size: 11pt; line-height: 1.85; padding-right: 0; }',
    '.colhead { font-family: Archivo, Arial, sans-serif; font-size: 8.5pt; color: #666; margin-bottom: 4pt; }',
    'p { margin: 0 0 8pt; orphans: 3; widows: 3; }',
    '.bw, .bwz { font-weight: 700; background: #fff3a8; -webkit-print-color-adjust: exact; print-color-adjust: exact; }',
    '.tip { display: none; }',
    'h2 { font-family: Archivo, Arial, sans-serif; font-size: 13pt; margin: 16pt 0 6pt; border-top: 1px solid #999; padding-top: 8pt; }',
    '.vocab-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6pt 14pt; }',
    '.vocab-item { break-inside: avoid; border: 1px solid #ccc; padding: 5pt 7pt; }',
    '.vocab-phrase { font-weight: 700; }',
    '.vocab-num { display: none; }',
    '.vocab-zh { font-family: "Noto Serif HK", serif; color: #333; }',
    '.vocab-sample { font-style: italic; color: #333; font-size: 10pt; }',
    'table.phrase-table, table.vlist { width: 100%; border-collapse: collapse; font-size: 10pt; }',
    'table.phrase-table th, table.phrase-table td, table.vlist th, table.vlist td { border: 1px solid #bbb; padding: 4pt 6pt; text-align: left; vertical-align: top; }',
    'table.phrase-table tr, table.vlist tr { break-inside: avoid; }',
    '.vocab-section-label, .causes-title, h2 { font-family: Archivo, Arial, sans-serif; font-weight: 700; margin: 10pt 0 4pt; break-after: avoid; page-break-after: avoid; }',
    '.angle-zh, .angle-zh-label { font-family: "Noto Serif HK", serif; color: #333; }',
    '.angle { margin-bottom: 6pt; break-inside: avoid; }',
    '.causes-list li { margin-bottom: 5pt; }',
    '.footer { margin-top: 18pt; font-family: Archivo, Arial, sans-serif; font-size: 8.5pt; color: #777; border-top: 1px solid #ccc; padding-top: 4pt; }',
    '.hint { font-family: Arial, sans-serif; background: #fffbe6; border: 1px solid #e5d27a; padding: 8pt 10pt; margin-bottom: 12pt; font-size: 10pt; }',
    '@media print { .hint { display: none; } }'
  ].join(' ');
  var PRINT_FONTS = 'https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=Source+Serif+4:wght@400;700&family=Noto+Serif+HK:wght@400;700&display=swap';

  function _esc(t) {
    return String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // Open the print tab straight away (inside the click) so pop-up blockers allow it
  function _openPrintWindow() {
    var w = window.open('', '_blank');
    if (!w) {
      alert('Your browser blocked the print page. Allow pop-ups for this site, then press Print again.');
      return null;
    }
    w.document.write('<p style="font-family:Arial,sans-serif;padding:2rem">Preparing your printout…</p>');
    return w;
  }

  function _fillPrintWindow(w, title, inner) {
    var today = new Date().toLocaleDateString('en-HK', { year: 'numeric', month: 'long', day: 'numeric' });
    w.document.open();
    w.document.write('<!doctype html><html lang="en"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width, initial-scale=1">' +
      '<title>' + _esc(title) + '</title><link rel="stylesheet" href="' + PRINT_FONTS + '">' +
      '<style>' + PRINT_CSS + '</style></head><body>' +
      '<div class="hint">To save a PDF, choose <b>Save as PDF</b> (or Microsoft Print to PDF) as the printer.</div>' +
      '<div class="brand"><span>HKDSE Daily 每日英語</span><span>' + _esc(today) + '</span></div>' +
      inner +
      '<div class="footer">buddygogo.github.io/hkdse-daily · For educational use</div>' +
      '</body></html>');
    w.document.close();
    var go = function() { try { w.focus(); w.print(); } catch (e) {} };
    if (w.document.fonts && w.document.fonts.ready) {
      w.document.fonts.ready.then(function() { setTimeout(go, 250); });
    } else {
      setTimeout(go, 900);
    }
  }

  // Library articles keep their full text in a/<id>.html until needed
  function _ensureLoaded(uid) {
    var src = document.getElementById('body-' + uid);
    if (!src) return Promise.reject(new Error('missing'));
    if (!src.dataset.src || src.dataset.loaded) return Promise.resolve(src);
    return fetch(src.dataset.src).then(function(r) {
      if (!r.ok) throw new Error(r.status);
      return r.text();
    }).then(function(html) {
      src.innerHTML = html;
      src.dataset.loaded = '1';
      if (window._applyUserState) window._applyUserState(src);
      return src;
    });
  }

  function printArticle(uid, mode) {
    var w = _openPrintWindow();
    if (!w) return;
    _ensureLoaded(uid).then(function(src) {
      var head = (document.getElementById('hl-' + uid) || {}).textContent || 'HKDSE Daily';
      var metaEl = document.getElementById('meta-' + uid);
      var meta = metaEl ? metaEl.innerText.trim() : '';

      var enEl = src.querySelector('.bi-en') || src.querySelector('.news-body, .trend-body, .card-summary');
      var zhEl = src.querySelector('.bi-zh');
      var en = enEl ? enEl.cloneNode(true) : document.createElement('div');
      en.querySelectorAll('.bi-label, .tip').forEach(function(x) { x.remove(); });
      var zh = zhEl ? zhEl.cloneNode(true) : null;
      if (zh) zh.querySelectorAll('.bi-label').forEach(function(x) { x.remove(); });

      var body;
      if (mode === 'both' && zh) {
        body = '<table class="bi"><tr><td class="en"><div class="colhead">English</div>' + en.innerHTML +
               '</td><td class="zh"><div class="colhead">中文翻譯</div>' + zh.innerHTML + '</td></tr></table>';
      } else {
        body = '<div class="en">' + en.innerHTML + '</div>';
      }

      // study notes: vocabulary, phrases, writing angles (no buttons or personal notes)
      var notes = '';
      var dr = src.querySelector('.study-drawer');
      if (dr) {
        var c = dr.cloneNode(true);
        c.querySelectorAll('.bi-grid, .article-note-section, .article-actions, .causes-block, button, .tip').forEach(function(x) { x.remove(); });
        if (c.textContent.trim()) notes += c.innerHTML;
      }
      var cb = src.querySelector('.causes-block');
      if (cb) notes += cb.outerHTML;
      if (notes) notes = '<h2>Study notes</h2>' + notes;

      _fillPrintWindow(w, head, '<h1>' + _esc(head) + '</h1><p class="meta">' + _esc(meta) + '</p>' + body + notes);
    }).catch(function() {
      w.close();
      alert('Could not load this article. Check your connection and try again.');
    });
  }

  function printSavedVocab() {
    var list = _loadSaved();
    if (!list.length) { alert('Your saved list is empty. Tap 💾 next to any word or phrase to save it.'); return; }
    var w = _openPrintWindow();
    if (!w) return;
    var rows = list.map(function(it, i) {
      return '<tr><td>' + (i + 1) + '</td><td><b>' + _esc(it.phrase) + '</b></td><td class="zh">' + _esc(it.zh) +
             '</td><td><i>' + _esc(it.sample) + '</i></td></tr>';
    }).join('');
    _fillPrintWindow(w, 'My saved vocabulary',
      '<h1>My saved vocabulary</h1><p class="meta">' + list.length + ' words and phrases</p>' +
      '<table class="vlist"><tr><th>#</th><th>Word / phrase</th><th>中文</th><th>Example sentence</th></tr>' + rows + '</table>');
  }

  // ── LISTEN (read the English article aloud) ─────────────────────────────
  var _listenBtn = null;
  function listenArticle(uid, btn) {
    if (!window.speechSynthesis) { alert('Your browser does not support reading aloud.'); return; }
    if (_listenBtn) {  // second tap stops
      var was = _listenBtn;
      window.speechSynthesis.cancel();
      _listenBtn.textContent = '🔊 Listen';
      _listenBtn = null;
      if (was === btn) return;
    }
    _ensureLoaded(uid).then(function(src) {
      var en = src.querySelector('.bi-en') || src.querySelector('.news-body, .trend-body, .card-summary');
      if (!en) return;
      var c = en.cloneNode(true);
      c.querySelectorAll('.tip, .bi-label').forEach(function(x) { x.remove(); });
      var u = new SpeechSynthesisUtterance(c.innerText);
      u.lang = 'en-GB'; u.rate = 0.9;
      u.onend = function() { if (_listenBtn) { _listenBtn.textContent = '🔊 Listen'; _listenBtn = null; } };
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
      _listenBtn = btn;
      btn.textContent = '⏹ Stop';
    });
  }

  // ── SHARE ─────────────────────────────────────────────────────────────────
  function _articleUrl(uid) {
    return location.origin + location.pathname + '#' + encodeURIComponent(uid);
  }

  function shareArticle(uid) {
    var head = ((document.getElementById('hl-' + uid) || {}).textContent || 'HKDSE Daily').trim();
    var url = _articleUrl(uid);
    var text = head + ' | HKDSE Daily 每日英語';
    var u = encodeURIComponent(url), t = encodeURIComponent(text);
    var links = [
      ['WhatsApp', 'https://wa.me/?text=' + t + '%20' + u],
      ['Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + u],
      ['Threads', 'https://www.threads.net/intent/post?text=' + t + '%20' + u],
      ['X', 'https://twitter.com/intent/tweet?text=' + t + '&url=' + u],
      ['Telegram', 'https://t.me/share/url?url=' + u + '&text=' + t],
      ['LINE', 'https://social-plugins.line.me/lineit/share?url=' + u],
      ['Email', 'mailto:?subject=' + t + '&body=' + t + '%0A%0A' + u]
    ];
    var grid = document.getElementById('share-grid');
    var sheet = document.getElementById('share-sheet');
    var status = document.getElementById('share-status');
    if (!grid || !sheet) return;
    grid.innerHTML = '';
    if (navigator.share) {
      var more = document.createElement('button');
      more.className = 'share-opt share-native';
      more.textContent = 'Share via phone…';
      more.onclick = function() { navigator.share({ title: head, text: text, url: url }).catch(function(){}); };
      grid.appendChild(more);
    }
    links.forEach(function(l) {
      var a = document.createElement('a');
      a.className = 'share-opt';
      a.href = l[1];
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = l[0];
      grid.appendChild(a);
    });
    var copy = document.createElement('button');
    copy.className = 'share-opt';
    copy.textContent = 'Copy link';
    copy.onclick = function() {
      var done = function() { status.textContent = 'Link copied. Paste it into Instagram, WeChat or any chat.'; };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function() { window.prompt('Copy this link:', url); });
      else window.prompt('Copy this link:', url);
    };
    grid.appendChild(copy);
    status.textContent = '';
    document.getElementById('share-head').textContent = head;
    sheet.hidden = false;
  }

  function closeShare() {
    var sheet = document.getElementById('share-sheet');
    if (sheet) sheet.hidden = true;
  }

  // Shared links (…/#<article id>) open that article directly
  window.addEventListener('load', function() {
    var id = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (id && document.getElementById('body-' + id)) openFull(id);
  });

  // On load: mark already-saved buttons and sync badge
  (function() {
    var list = _loadSaved();
    _updateBadge();
    if (list.length === 0) return;
    var phrases = list.map(function(x){ return x.phrase; });
    document.querySelectorAll('.save-vocab-btn, .save-vocab-btn-sm').forEach(function(b) {
      var onclick = b.getAttribute('onclick') || '';
      phrases.forEach(function(ph) {
        if (onclick.indexOf(ph.replace(/'/g,"\\'")) !== -1) {
          b.classList.add('saved'); b.title = 'Saved! Click to remove';
        }
      });
    });
  })();

  // ── FULL-SCREEN ARTICLE / TREND VIEWER ──────────────────────────────────────
  // Library articles load their full text on demand from a/<id>.html
  function openFull(uid) {
    var srcBody = document.getElementById('body-' + uid);
    if (srcBody && srcBody.dataset.src && !srcBody.dataset.loaded) {
      srcBody.classList.add('loading');
      fetch(srcBody.dataset.src).then(function(r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      }).then(function(html) {
        srcBody.innerHTML = html;
        srcBody.dataset.loaded = '1';
        srcBody.classList.remove('loading');
        _openFullNow(uid);
      }).catch(function() {
        srcBody.classList.remove('loading');
        alert('Could not load this article. Check your connection and try again.');
      });
      return;
    }
    _openFullNow(uid);
  }

  var _scrollBeforeFull = 0;
  function _openFullNow(uid) {
    var overlay = document.getElementById('full-overlay');
    if (overlay && !overlay.classList.contains('open')) {
      _scrollBeforeFull = window.scrollY;
      window.scrollTo(0, 0);
    }
    var strip = document.querySelector('.site-header');
    if (overlay && strip) overlay.style.top = Math.round(strip.getBoundingClientRect().bottom) + 'px';
    var headEl  = document.getElementById('full-headline');
    var metaEl  = document.getElementById('full-meta');
    var bodyEl  = document.getElementById('full-body');
    if (!overlay) return;

    // Source elements
    var srcHead = document.getElementById('hl-'   + uid);
    var srcMeta = document.getElementById('meta-' + uid);
    var srcBody = document.getElementById('body-' + uid);

    headEl.textContent = srcHead ? srcHead.textContent : '';
    var coverEl = document.getElementById('full-cover');
    if (coverEl) {
      coverEl.innerHTML = '';
      var holder = srcHead && srcHead.closest('article, section');
      var img = holder && holder.querySelector('img');
      if (img && img.getAttribute('src')) {
        var im = document.createElement('img'); im.src = img.getAttribute('src'); im.alt = '';
        coverEl.appendChild(im);
      }
    }
    metaEl.innerHTML   = srcMeta ? srcMeta.innerHTML   : '';

    if (srcBody) {
      var clone = srcBody.cloneNode(true);
      // Force all study drawers open
      clone.querySelectorAll('.study-drawer').forEach(function(d){ d.style.display = 'block'; });
      // Hide toggle buttons — content is always visible in full view
      clone.querySelectorAll('.study-toggle, .trend-study-toggle').forEach(function(t){ t.style.display = 'none'; });
      // Avoid duplicate IDs: the overlay copy gets its own
      clone.removeAttribute('id');
      clone.querySelectorAll('[id]').forEach(function(el){ el.id = 'full-' + el.id; });
      bodyEl.innerHTML = '';
      bodyEl.appendChild(clone);
      setLang(_lang);
      if (window._applyUserState) window._applyUserState(clone);
    }

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeFull() {
    var overlay = document.getElementById('full-overlay');
    var wasOpen = overlay && overlay.classList.contains('open');
    if (overlay) overlay.classList.remove('open');
    document.body.style.overflow = '';
    if (wasOpen) window.scrollTo(0, _scrollBeforeFull);
    if (window.speechSynthesis && _listenBtn) { window.speechSynthesis.cancel(); _listenBtn.textContent = '🔊 Listen'; _listenBtn = null; }
  }

  // Paired highlights: English phrase N <-> Chinese phrase N within the same article
  function _pairToggle(el, on) {
    var grid = el.closest('.bi-grid');
    if (!grid) return;
    grid.querySelectorAll('[data-k="' + el.dataset.k + '"]').forEach(function(x) {
      if (x.classList.contains('bw') || x.classList.contains('bwz')) x.classList.toggle('pair-on', on);
    });
  }
  document.addEventListener('mouseover', function(e) {
    var el = e.target.closest && e.target.closest('.bw[data-k], .bwz[data-k]');
    if (el) _pairToggle(el, true);
  });
  document.addEventListener('mouseout', function(e) {
    var el = e.target.closest && e.target.closest('.bw[data-k], .bwz[data-k]');
    if (el) _pairToggle(el, false);
  });
  document.addEventListener('click', function(e) {
    var el = e.target.closest && e.target.closest('.bw[data-k], .bwz[data-k]');
    if (!el) return;
    var grid = el.closest('.bi-grid');
    if (!grid) return;
    var wasOn = el.classList.contains('pair-on') && el.dataset.tapped === '1';
    grid.querySelectorAll('.pair-on').forEach(function(x){ x.classList.remove('pair-on'); x.dataset.tapped = ''; });
    if (!wasOn) { _pairToggle(el, true); el.dataset.tapped = '1'; }
  });

  // Close on Escape key
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeFull();
  });

  // ── FIREBASE: GOOGLE AUTH + FIRESTORE SYNC ───────────────────────────────
  (function() {
    var FB_CONFIG = {
      apiKey: "AIzaSyDJCiCOCJUOMHRzvInUBCeJU6NUewbPKGM",
      authDomain: "hkdse-daily.firebaseapp.com",
      projectId: "hkdse-daily",
      storageBucket: "hkdse-daily.firebasestorage.app",
      messagingSenderId: "993113747556",
      appId: "1:993113747556:web:65e4738a200f0ec154af71"
    };

    function initFirebase() {
      if (typeof firebase === 'undefined') { setTimeout(initFirebase, 200); return; }
      try { firebase.app(); } catch(e) { firebase.initializeApp(FB_CONFIG); }
      var auth = firebase.auth();
      var db   = firebase.firestore();
      window._fb = { auth: auth, db: db };

      auth.onAuthStateChanged(function(user) {
        var loginBtn  = document.getElementById('auth-login-btn');
        var userPill  = document.getElementById('auth-user-pill');
        if (user) {
          if (loginBtn) loginBtn.style.display = 'none';
          if (userPill) {
            userPill.style.display = 'flex';
            var av = userPill.querySelector('.auth-avatar');
            var nm = userPill.querySelector('.auth-user-name');
            if (av) av.textContent = (user.displayName || user.email || '?').trim().charAt(0).toUpperCase();
            if (nm) nm.textContent = user.displayName || user.email;
          }
          var tm = document.getElementById('tab-me');
          if (tm) tm.lastChild.textContent = 'Sign out';
          _loadCloudVocab(user.uid);
          _loadCloudNotes(user.uid);
        } else {
          if (loginBtn) loginBtn.style.display = 'flex';
          if (userPill) userPill.style.display = 'none';
          _notesCache = {};
        }
        _applyUserState(document);
      });
    }
    initFirebase();

    var _notesCache = {};

    // Sync note boxes and saved-vocab highlights inside `root`
    // (the page, a lazily loaded article, or the full-screen copy)
    function _applyUserState(root) {
      var signedIn = !!(window._fb && window._fb.auth.currentUser);
      root.querySelectorAll('.article-note-section').forEach(function(sec) {
        var hint = sec.querySelector('.note-login-hint');
        var area = sec.querySelector('.note-textarea');
        var row  = sec.querySelector('.note-save-row');
        if (hint) hint.style.display = signedIn ? 'none' : '';
        if (area) {
          area.style.display = signedIn ? 'block' : 'none';
          var key = sec.dataset.note;
          if (signedIn && key && _notesCache[key] !== undefined && !area.value) area.value = _notesCache[key];
        }
        if (row) row.style.display = signedIn ? 'flex' : 'none';
      });
      var saved = _loadSaved().map(function(x){ return x.phrase.replace(/'/g,"\'"); });
      root.querySelectorAll('.save-vocab-btn, .save-vocab-btn-sm').forEach(function(b) {
        var oc = b.getAttribute('onclick') || '';
        if (saved.some(function(p){ return oc.indexOf("'" + p + "'") !== -1; })) b.classList.add('saved');
      });
    }
    window._applyUserState = _applyUserState;

    var _SIGNIN_MESSAGES = {
      'auth/popup-blocked': 'Your browser blocked the sign-in window. Allow pop-ups for this site, then tap Sign in again.',
      'auth/operation-not-allowed': 'Google sign-in is not switched on for this site yet. Please tell your teacher.',
      'auth/unauthorized-domain': 'Sign-in is not enabled for this web address yet. Please tell your teacher.',
      'auth/network-request-failed': 'No connection to Google. Check your internet and try again.',
      'auth/web-storage-unsupported': 'This browser blocks sign-in. Open the site in Chrome or Safari instead.',
      'auth/operation-not-supported-in-this-environment': 'Sign-in does not work inside this app. Open the site in Chrome or Safari instead.'
    };
    window.signInWithGoogle = function() {
      if (!window._fb) { alert('Sign-in is still loading. Try again in a moment.'); return; }
      var provider = new firebase.auth.GoogleAuthProvider();
      provider.setCustomParameters({ prompt: 'select_account' });
      window._fb.auth.signInWithPopup(provider).catch(function(e) {
        if (e.code === 'auth/popup-closed-by-user' || e.code === 'auth/cancelled-popup-request') return;
        alert(_SIGNIN_MESSAGES[e.code] || ('Sign-in failed (' + (e.code || e.message) + '). Try again.'));
      });
    };
    window.signOutGoogle = function() {
      if (!window._fb) return;
      if (confirm('Sign out?')) window._fb.auth.signOut();
    };

    function _loadCloudVocab(uid) {
      window._fb.db.collection('users').doc(uid).collection('vocab')
        .get().then(function(snap) {
          var localList = _loadSaved();
          snap.forEach(function(doc) {
            var d = doc.data();
            if (d.phrase && !localList.some(function(x){ return x.phrase === d.phrase; })) {
              localList.push(d);
            }
          });
          _saveSaved(localList);
          _updateBadge();
          _applyUserState(document);
        }).catch(function(){});
    }

    function _loadCloudNotes(uid) {
      window._fb.db.collection('users').doc(uid).collection('notes')
        .get().then(function(snap) {
          snap.forEach(function(doc) { _notesCache[doc.id] = doc.data().text || ''; });
          _applyUserState(document);
        }).catch(function(){});
    }

    // Patch saveVocab to also write/delete in Firestore
    var _origSaveVocab = window.saveVocab;
    window.saveVocab = function(phrase, zh, sample, btn) {
      _origSaveVocab(phrase, zh, sample, btn);
      if (!window._fb) return;
      var user = window._fb.auth.currentUser;
      if (!user) return;
      var docId = phrase.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 80);
      var nowInList = _loadSaved().some(function(x){ return x.phrase === phrase; });
      var ref = window._fb.db.collection('users').doc(user.uid).collection('vocab').doc(docId);
      if (nowInList) {
        ref.set({ phrase: phrase, zh: zh, sample: sample, saved: firebase.firestore.FieldValue.serverTimestamp() }).catch(function(){});
      } else {
        ref.delete().catch(function(){});
      }
    };

    var _origRemoveSaved = window.removeSaved;
    window.removeSaved = function(phrase) {
      _origRemoveSaved(phrase);
      if (!window._fb) return;
      var user = window._fb.auth.currentUser;
      if (!user) return;
      var docId = phrase.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 80);
      window._fb.db.collection('users').doc(user.uid).collection('vocab').doc(docId).delete().catch(function(){});
    };

    // Notes are keyed by the article's permanent id, so they follow it into the library
    window.saveNote = function(noteKey, btn) {
      if (!window._fb) return;
      var user = window._fb.auth.currentUser;
      if (!user) return;
      var sec    = btn ? btn.closest('.article-note-section') : null;
      var area   = sec ? sec.querySelector('.note-textarea') : null;
      var status = sec ? sec.querySelector('.note-status') : null;
      if (!area) return;
      _notesCache[noteKey] = area.value;
      // keep the other copy (card vs full-screen) in step
      document.querySelectorAll('.article-note-section[data-note="' + noteKey + '"] .note-textarea').forEach(function(t){
        if (t !== area) t.value = area.value;
      });
      window._fb.db.collection('users').doc(user.uid).collection('notes').doc(noteKey)
        .set({ text: area.value, updated: firebase.firestore.FieldValue.serverTimestamp() })
        .then(function() {
          if (status) { status.textContent = 'Saved ✓'; setTimeout(function(){ status.textContent = ''; }, 2000); }
        }).catch(function() {
          if (status) status.textContent = 'Could not save. Check your connection and try again.';
        });
    };
  })();
"""

# ── HTML TEMPLATE ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <meta name="theme-color" content="#111418" />
  <title>HKDSE Daily Brief</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&family=Archivo:wdth,wght@100..125,400..800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400&family=Noto+Serif+HK:wght@400;600&family=Noto+Sans+HK:wght@400;500;700&display=swap" rel="stylesheet" />
  <style>{css}</style>
</head>
<body>

<div class="site-header">
<!-- TOP BAR -->
<header class="topbar">
  <div class="topbar-inner">
    <div class="logo">
      <div class="logo-mark">📰</div>
      <span class="logo-name" onclick="closeFull()" style="cursor:pointer">HKDSE Daily</span><span class="logo-zh">每日英語</span>
    </div>
    <div class="topbar-right">
      <div class="topbar-date"><strong id="today-date">Loading…</strong></div>
      <button id="auth-login-btn" class="auth-login-btn" onclick="signInWithGoogle()" title="Sign in to sync vocab & notes across devices">
        <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#fff"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#fff" opacity=".85"/><path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#fff" opacity=".7"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#fff" opacity=".55"/></svg>
        Sign in
      </button>
      <div id="auth-user-pill" class="auth-user-pill" onclick="signOutGoogle()" title="Click to sign out">
        <span class="auth-avatar" aria-hidden="true"></span>
        <span class="auth-user-name"></span>
      </div>
      <button class="btn-open-saved" onclick="toggleSavedPanel()" title="My saved vocab list">
        💾 My Vocab <span class="saved-count-badge" id="saved-count-badge"></span>
      </button>
    </div>
  </div>
</header>

<nav class="topic-nav" aria-label="Topics"><div class="topic-inner">{topic_nav}</div></nav>
</div>
<div class="news-update"><span class="nu-label">News update</span>{ticker}</div>

<!-- SAVED VOCAB PANEL -->
<div class="saved-panel-overlay" id="saved-panel-overlay" onclick="if(event.target===this)toggleSavedPanel()">
  <div class="saved-panel">
    <div class="saved-panel-head">
      <span class="saved-panel-title">💾 My Saved Vocab</span>
      <div class="saved-panel-actions">
        <button class="btn-clear-saved" onclick="clearSaved()">Clear All</button>
        <button class="btn-print-saved" onclick="printSavedVocab()">🖨️ Print / Save PDF</button>
        <button class="saved-panel-close" onclick="toggleSavedPanel()">✕</button>
      </div>
    </div>
    <div class="saved-panel-body" id="saved-panel-body">
      <div class="saved-empty">💡 Tap 💾 on any vocab or phrase to save it here for revision.<br><br>Your saved list is stored in this browser — no account needed.</div>
    </div>
  </div>
</div>

<!-- SHARE MENU -->
<div class="share-sheet" id="share-sheet" hidden onclick="if(event.target===this)closeShare()">
  <div class="share-box" role="dialog" aria-labelledby="share-head">
    <div class="share-label">Share this article</div>
    <div class="share-head" id="share-head"></div>
    <div class="share-grid" id="share-grid"></div>
    <div class="share-status" id="share-status" aria-live="polite"></div>
    <button class="share-close" onclick="closeShare()">Close</button>
  </div>
</div>

<!-- FULL-SCREEN ARTICLE OVERLAY -->
<div class="full-overlay" id="full-overlay" onclick="if(event.target===this)closeFull()">
  <div class="full-overlay-inner">
    <div class="full-overlay-topbar">
      <button class="full-close-btn" onclick="closeFull()">← Back</button>
    </div>
    <div class="full-cover" id="full-cover"></div>
    <h2 class="full-headline" id="full-headline"></h2>
    <div class="full-meta" id="full-meta"></div>
    <div class="lang-switch" role="group" aria-label="Language">
      <button class="on" data-lang="both" onclick="setLang('both', this)">Both</button>
      <button data-lang="en" onclick="setLang('en', this)">English</button>
      <button data-lang="zh" onclick="setLang('zh', this)">中文</button>
    </div>
    <div class="full-body" id="full-body"></div>
  </div>
</div>

<main class="mag">
  {hero}

  <section class="mag-section">
    <div class="mag-head">
      <h2 class="mag-h2">Featured stories</h2>
      <div class="mag-arrows home-only">
        <button class="mag-arrow" onclick="scrollRail(-1)" aria-label="Previous stories">←</button>
        <button class="mag-arrow" onclick="scrollRail(1)" aria-label="Next stories">→</button>
      </div>
    </div>
    <div class="mag-rail" id="mag-rail">{featured}
    </div>
  </section>

  <div class="mag-split">
    <section class="mag-section mag-latest">
      <div class="mag-head"><h2 class="mag-h2">The latest</h2></div>
      {latest}
    </section>
    <aside class="mag-side home-only">
      {trending}
      {countdown_sidebar}
    </aside>
  </div>

  <div class="mag-section mag-trends">{trends_main}</div>
  {library}
</main>

<nav class="tabbar" aria-label="App navigation">
  <button class="tab on" id="tab-home" onclick="tabTo('home', this)"><span class="tab-ico">⌂</span>Home</button>
  <button class="tab" onclick="tabTo('topics', this)"><span class="tab-ico">☰</span>Topics</button>
  <button class="tab" onclick="tabTo('vocab', this)"><span class="tab-ico">💾</span>My Vocab</button>
  <button class="tab" id="tab-me" onclick="tabTo('me', this)"><span class="tab-ico">👤</span>Sign in</button>
</nav>
<footer class="mag-footer">
  <div class="mag-footer-inner">
    <div><div class="mag-footer-brand">HKDSE Daily <span>每日英語</span></div>
      <p>Real Hong Kong news, written for HKDSE English Paper 2. Every article in English and 中文, with vocabulary, phrases and essay angles.</p></div>
    <div class="mag-footer-tips"><b>How to use</b><span>Hover or tap highlighted words for meanings</span><span>🔊 to hear pronunciation · 💾 to save words</span><span>🖨 Print any article for revision</span></div>
  </div>
  <div class="mag-footer-small">For educational use only</div>
</footer>

<!-- Firebase SDKs (compat version — works without bundler) -->
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>
<script>{js}</script>
</body>
</html>"""


# ── MAGAZINE HOMEPAGE (layout modelled on the user's reference designs) ─────

def _read_time(a: dict) -> str:
    words = len(re.sub(r"<[^>]+>", " ", a.get("summary_html", "")).split())
    return f"{max(1, round(words / 200))} min read"


def _cat_label(a: dict) -> str:
    return _TAG_META.get(_first_cat(a), ("", "News"))[1]


def _hidden_body(a: dict, uid: str) -> str:
    """Full article (EN + 中文 + notes + actions) loads on demand from a/<uid>.html."""
    _FRAGMENTS[uid] = (
        _bilingual_html(a.get("summary_html", ""), a.get("summary_zh_html", ""), "news-body")
        + _study_notes_html(a, uid)
        + _actions_html(uid)
    )
    return f'<div id="body-{uid}" data-src="a/{uid}.html" hidden></div>'


def _meta_html(a: dict, uid: str, cls: str = "mag-meta") -> str:
    src = a.get("source_name", "")
    day = _nice_date(a.get("date", "")) or a.get("published_date", "")
    return (f'<div class="{cls}" id="meta-{uid}"><span class="mag-src">{src}</span>'
            f'<span class="mag-dot"></span><span>{day}</span></div>')


def _pill(a: dict) -> str:
    col = _LINE_COLOURS.get(_first_cat(a), "#151922")
    return f'<span class="mag-pill" style="--line:{col}">{_cat_label(a)}</span>'


def _img(a: dict, cls: str) -> str:
    return _cover_html(a, None, cls, "cover-mag")


def build_hero_mag(a: dict, others: list[dict]) -> str:
    uid = a.get("id") or "hero"
    hl = a.get("headline", "")
    strip = "".join(
        f'<button class="hero-next" onclick="openFull(\'{o.get("id")}\')">'
        f'<span class="hero-next-num">{i}</span><span>{o.get("headline", "")}</span></button>'
        for i, o in enumerate(others[:4], 2)
    )
    media = (f'<img class="mag-hero-img" src="{a["banner"]}" alt="" onerror="this.remove()">'
             if a.get("banner") else _img(a, "mag-hero-img"))
    return f"""
  <section class="mag-hero" data-cat="{' '.join((a.get('category') or 'social').split())}">
    <div class="mag-hero-media" onclick="openFull('{uid}')">{media}</div>
    <div class="mag-hero-shade"></div>
    <div class="mag-hero-text">
      <div class="mag-hero-pills"><span class="mag-pill mag-pill-glass">Today's top story</span>{_pill(a)}</div>
      <h1 class="mag-hero-title clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{hl}</h1>
      <div class="mag-hero-read">
        <button class="mag-read-btn" onclick="openFull('{uid}')" aria-label="Read story">→</button>
        <span>Read story</span><span class="mag-dot"></span><span>{_read_time(a)}</span>
      </div>
      {_meta_html(a, uid, "mag-meta mag-meta-hero")}
    </div>
    {f'<div class="mag-hero-strip home-only">{strip}</div>' if strip else ''}
    {_hidden_body(a, uid)}
  </section>"""


def _feature_card(a: dict) -> str:
    uid = a.get("id")
    return f"""
      <article class="mag-feature" data-cat="{' '.join((a.get('category') or 'social').split())}" onclick="openFull('{uid}')">
        <div class="mag-feature-media">{_img(a, "mag-feature-img")}</div>
        <div class="mag-feature-shade"></div>
        {_pill(a)}
        <div class="mag-feature-text">
          <h3 class="mag-feature-title" id="hl-{uid}">{a.get('headline', '')}</h3>
          {_meta_html(a, uid, "mag-meta mag-meta-light")}
        </div>
        {_hidden_body(a, uid)}
      </article>"""


def _list_item(a: dict) -> str:
    uid = a.get("id")
    return f"""
      <article class="mag-list-item" data-cat="{' '.join((a.get('category') or 'social').split())}">
        <div class="mag-list-thumb" onclick="openFull('{uid}')">{_img(a, "mag-list-img")}</div>
        <div class="mag-list-text">
          <h3 class="mag-list-title clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{a.get('headline', '')}</h3>
          <p class="mag-excerpt" onclick="openFull('{uid}')">{_excerpt(a.get('summary_html', ''), 26)}</p>
          <div class="mag-list-foot">{_pill(a)}<span>{_nice_date(a.get('date', ''))}</span><span class="mag-dot"></span><span>{_read_time(a)}</span></div>
          <div hidden>{_meta_html(a, uid)}</div>
        </div>
        {_hidden_body(a, uid)}
      </article>"""


def _grid_card(a: dict) -> str:
    uid = a.get("id")
    return f"""
      <article class="mag-card" data-cat="{' '.join((a.get('category') or 'social').split())}">
        <div class="mag-card-media" onclick="openFull('{uid}')">{_img(a, "mag-card-img")}</div>
        {_meta_html(a, uid)}
        <h3 class="mag-card-title clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{a.get('headline', '')}</h3>
        <p class="mag-excerpt" onclick="openFull('{uid}')">{_excerpt(a.get('summary_html', ''), 30)}</p>
        <div class="mag-card-foot"><span class="mag-cat-text" style="--line:{_LINE_COLOURS.get(_first_cat(a), '#151922')}">{_cat_label(a)}</span><span class="mag-dot"></span><span>{_read_time(a)}</span></div>
        {_hidden_body(a, uid)}
      </article>"""


def build_topic_nav(articles: list[dict], trends: list[dict]) -> str:
    have = {_first_cat(a) for a in articles}
    items = ['<button class="line-stop active" data-cat="all" onclick="filterCards(\'all\',this)">Home</button>']
    if trends:
        items.append('<button class="line-stop" data-cat="trends" onclick="filterCards(\'trends\',this)">Social trends</button>')
    for cat in _CAT_ORDER:
        if cat in have:
            items.append(f'<button class="line-stop" data-cat="{cat}" onclick="filterCards(\'{cat}\',this)" '
                         f'style="--line:{_LINE_COLOURS[cat]}">{_TAG_META.get(cat, ("", cat))[1]}</button>')
    return "".join(items)


def build_ticker(articles: list[dict]) -> str:
    items = "".join(
        f'<button class="tick-item" onclick="openFull(\'{a.get("id")}\')">{a.get("headline", "")}</button>'
        for a in articles[:8]
    )
    return f'<div class="tick-track"><div class="tick-run">{items}</div><div class="tick-run" aria-hidden="true">{items}</div></div>'


def build_trending(trends: list[dict]) -> str:
    rows = "".join(
        f'<button class="trend-row" onclick="openFull(\'{t.get("id")}\')"><span class="trend-num">#{i}</span>'
        f'<span class="trend-row-text"><span class="trend-row-title">{t.get("headline", "")}</span>'
        f'<span class="trend-row-meta">{_nice_date(t.get("date", ""))}<span class="mag-dot"></span>4 essay angles</span></span></button>'
        for i, t in enumerate(trends[:6], 1)
    )
    return f'<div class="trending-box"><h2 class="mag-h2 trending-h">On trending 🔥</h2>{rows}</div>'


ARCHIVE_FILE = "archive.json"
_CAT_ORDER = ["tech", "school", "env", "hk", "pop", "social", "econ", "health",
              "global", "urban", "law", "career", "sports", "arts", "family"]


def load_archive(path: str = ARCHIVE_FILE) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            arc = json.load(f)
    else:
        arc = {}
    arc.setdefault("articles", [])
    arc.setdefault("trends", [])
    return arc


def save_archive(arc: dict, path: str = ARCHIVE_FILE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arc, f, ensure_ascii=False, indent=1)


def _item_id(prefix: str, headline: str) -> str:
    import hashlib
    return prefix + hashlib.md5(headline.strip().lower().encode()).hexdigest()[:8]


def merge_into_archive(arc: dict, data: dict, day: str) -> dict:
    """Add a day's articles/trends to the archive (skips duplicates by headline or URL)."""
    have_hl  = {a.get("headline", "").strip().lower() for a in arc["articles"]}
    have_url = {a.get("source_url") for a in arc["articles"] if a.get("source_url")}
    for a in data.get("articles", []):
        hl = a.get("headline", "").strip().lower()
        if not hl or hl in have_hl or (a.get("source_url") and a["source_url"] in have_url):
            continue
        a["date"] = day
        a["id"] = _item_id("a", hl)
        arc["articles"].append(a)
        have_hl.add(hl)
    have_t = {t.get("headline", "").strip().lower() for t in arc["trends"]}
    for t in data.get("trends", []):
        hl = t.get("headline", "").strip().lower()
        if not hl or hl in have_t:
            continue
        t["date"] = day
        t["id"] = _item_id("t", hl)
        arc["trends"].append(t)
        have_t.add(hl)
    if data.get("exam_date"):
        arc["exam_date"] = data["exam_date"]
    return arc


def apply_backfill(arc: dict, patch: dict) -> int:
    """patch = {"<id>": {field: value, ...}} — overwrites fields and clears needs_backfill."""
    n = 0
    for item in arc["articles"] + arc["trends"]:
        upd = patch.get(item.get("id"))
        if upd:
            item.update(upd)
            item.pop("needs_backfill", None)
            n += 1
    return n



def _sorted_newest(items: list[dict]) -> list[dict]:
    # stable sort: newest date first, original order kept within a day
    return sorted(items, key=lambda x: x.get("date", ""), reverse=True)


def build_page(data: dict) -> str:
    """Assemble the magazine-style homepage. `data` is the archive."""
    exam_date, _, is_estimated = get_next_exam_date()
    raw_exam = data.get("exam_date")
    if raw_exam and raw_exam != "null":
        try:
            found = date.fromisoformat(raw_exam)
            if found > date.today():
                exam_date, is_estimated = found, False
        except ValueError:
            pass

    articles = data.get("articles", [])
    newest = _sorted_newest(articles)
    latest = newest[0].get("date", "") if newest else ""
    today = [a for a in articles if a.get("date", "") == latest]
    older = [a for a in newest if a.get("date", "") != latest]

    hero = build_hero_mag(today[0], today[1:]) if today else ""
    featured = today[1:] + older[:8]
    latest_list = older[8:14]
    rest = older[14:]

    featured_html = "".join(_feature_card(a) for a in featured)
    latest_html = "".join(_list_item(a) for a in latest_list)

    library_html = ""
    for cat in _CAT_ORDER:
        items = [a for a in rest if _first_cat(a) == cat]
        if not items:
            continue
        lbl = _TAG_META.get(cat, ("", cat))[1]
        library_html += f"""
  <section class="mag-section">
    <div class="mag-head"><h2 class="mag-h2" style="--line:{_LINE_COLOURS.get(cat, '#151922')}">{lbl}</h2></div>
    <div class="mag-grid">{''.join(_grid_card(a) for a in items)}
    </div>
  </section>"""

    trends = _sorted_newest(data.get("trends", []))
    countdown_html = build_countdown_widget_html(exam_date, is_estimated)

    return HTML_TEMPLATE.format(
        css=CSS,
        js=JS,
        topic_nav=build_topic_nav(articles, trends),
        ticker=build_ticker(newest),
        hero=hero,
        featured=featured_html,
        latest=latest_html,
        trending=build_trending(trends),
        trends_main=build_trend_main_html(trends),
        library=library_html,
        countdown_sidebar=countdown_html,
    )


def _write_index(arc: dict) -> None:
    _FRAGMENTS.clear()
    html = build_page(arc)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    os.makedirs("a", exist_ok=True)
    for old in os.listdir("a"):
        if old.endswith(".html") and old[:-5] not in _FRAGMENTS:
            os.remove(os.path.join("a", old))
    for uid, frag in _FRAGMENTS.items():
        with open(os.path.join("a", f"{uid}.html"), "w", encoding="utf-8") as f:
            f.write(frag)
    print(f"✅ Built {OUTPUT_FILE}: {len(arc['articles'])} articles, {len(arc['trends'])} trends")


def cli() -> bool:
    """Archive workflow used by the cloud routine and GitHub Actions.
       --merge data.json [YYYY-MM-DD]   add a day's content to archive.json and rebuild
       --backfill patch.json            apply fixes to old items and rebuild
       --covers                         fetch missing cover photos and rebuild
       --build                          rebuild index.html from archive.json
    """
    args = sys.argv[1:]
    if not args:
        return False
    arc = load_archive()
    if args[0] == "--merge":
        with open(args[1], encoding="utf-8") as f:
            data = json.load(f)
        from datetime import timezone, timedelta
        day = args[2] if len(args) > 2 else datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        merge_into_archive(arc, data, day)
    elif args[0] == "--backfill":
        with open(args[1], encoding="utf-8") as f:
            print("  patched", apply_backfill(arc, json.load(f)), "items")
    elif args[0] != "--build":
        print(cli.__doc__)
        sys.exit(2)
    save_archive(arc)
    _write_index(arc)
    return True


def main() -> None:
    if cli():
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌  ANTHROPIC_API_KEY is not set.")
        print("    Export it:  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    print("🚀 HKDSE Daily Brief Generator")
    print(f"   {datetime.now().strftime('%A, %d %B %Y')}")
    print()

    data = generate_content()
    n_art   = len(data.get("articles", []))
    n_trend = len(data.get("trends",   []))
    print(f"  ✓ Content: {n_art} articles, {n_trend} trends")

    print("  🏗  Building HTML…")
    html = build_page(data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Saved → {OUTPUT_FILE}")
    print(f"   Open:  start {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
