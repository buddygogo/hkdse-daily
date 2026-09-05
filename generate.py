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
      <div class="article-note-section">
        <div class="note-label">✏️ My Notes</div>
        <p class="note-login-hint">
          <button onclick="signInWithGoogle()">Sign in with Google</button> to save personal notes for this article
        </p>
        <textarea class="note-textarea" id="note-area-{uid}" placeholder="Write your own notes, essay ideas, or vocabulary reminders here…"></textarea>
        <div class="note-save-row">
          <button class="note-save-btn" onclick="saveNote('{uid}')">Save Note</button>
          <span class="note-status" id="note-status-{uid}"></span>
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

    img_html = ""
    if image_url:
        safe = image_url.replace('"', '%22')
        alt  = article.get("headline", "").replace('"', '')
        img_html = f'<img class="hero-img" src="{safe}" alt="{alt}" loading="eager" onerror="this.parentElement.classList.add(\'no-img\')">'
    else:
        img_html = '<div class="hero-img-placeholder"></div>'

    study = _study_notes_html(article, uid)

    hl_esc = article.get('headline','').replace("'", "&#39;")

    return f"""
  <article class="hero-card" data-cat="{data_cat}">
    <div class="hero-media">
      {img_html}
      <div class="hero-overlay"></div>
      <div class="hero-overlay-text">
        <span class="cat-chip {tag_cls}">{tag_em} {tag_lbl}</span>
        <h2 class="hero-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{article.get('headline','')}</h2>
        <div class="hero-byline" id="meta-{uid}">
          <a class="hero-source" href="{src_url}" target="_blank" rel="noopener">{src_name}</a>
          {ig_badge}
          {f'<span class="hero-dot">·</span><span class="hero-pub">{pub}</span>' if pub else ''}
        </div>
      </div>
    </div>
    <div class="hero-body" id="body-{uid}">
      <div class="news-body">{article.get('summary_html','')}</div>
      {study}
    </div>
  </article>"""


def build_article_card_html(article: dict, image_url: str | None, uid: str) -> str:
    """Subsequent articles as compact grid cards."""
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

    img_html = ""
    if image_url:
        safe = image_url.replace('"', '%22')
        alt  = article.get("headline", "").replace('"', '')
        img_html = f'<div class="card-thumb-wrap"><img class="card-thumb" src="{safe}" alt="{alt}" loading="lazy" onerror="this.parentElement.style.display=\'none\'"></div>'

    study = _study_notes_html(article, uid)

    return f"""
  <article class="article-card" data-cat="{data_cat}">
    {img_html}
    <div class="card-body">
      <span class="cat-chip {tag_cls}">{tag_em} {tag_lbl}</span>
      <h3 class="card-headline clickable-headline" id="hl-{uid}" onclick="openFull('{uid}')">{article.get('headline','')}</h3>
      <div class="card-meta" id="meta-{uid}">
        <a class="card-source" href="{src_url}" target="_blank" rel="noopener">{src_name}</a>
        {ig_badge}
        {f'<span class="card-dot">·</span><span class="card-pub">{pub}</span>' if pub else ''}
      </div>
      <div id="body-{uid}">
        <div class="card-summary news-body">{article.get('summary_html','')}</div>
        {study}
      </div>
    </div>
  </article>"""


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
    uid = f"strend-{idx}"  # 'strend' = sidebar trend (avoid ID collision with main feed trends)
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
        <div class="trend-body">{trend.get('summary_html','')}</div>
        <div class="causes-block">
          <div class="causes-title">HKDSE Writing Angles</div>
          <ul class="causes-list">{causes_html}</ul>
        </div>
      </div>
    </div>
  </div>"""


def build_trend_main_html(trends: list[dict]) -> str:
    """Renders social trends as a full-width main-feed section."""
    if not trends:
        return ""
    items_html = ""
    for idx, trend in enumerate(trends):
        uid = f"trend-{idx}"
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
    <div id="meta-{uid}" style="display:none"><span>Social Trend</span></div>
    <div id="body-{uid}">
      <div class="trend-body">{trend.get('summary_html','')}</div>
      <div class="causes-block">
        <div class="causes-title">HKDSE Writing Angles</div>
        <ul class="causes-list">{causes_html}</ul>
      </div>
    </div>
  </div>"""
    return f"""
  <div class="main-section-head" data-cat="trends">
    <h2>📲 Social Trends</h2>
    <span class="section-see-all">Trending now</span>
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
    .auth-avatar { width: 24px; height: 24px; border-radius: 50%; object-fit: cover; }
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
    document.querySelectorAll('.sidebar-link[data-cat], .nav-tab[data-cat]').forEach(function(b) {
      b.classList.toggle('active', b.dataset.cat === cat);
    });
    document.querySelectorAll('[data-cat]').forEach(function(c) {
      if (c.classList.contains('sidebar-link') || c.classList.contains('nav-tab')) return;
      c.style.display = (cat === 'all' || c.dataset.cat.split(' ').includes(cat)) ? '' : 'none';
    });
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

  function printSavedVocab() {
    renderSavedPanel();
    document.body.classList.add('print-saved-mode');
    // make overlay temporarily visible for print
    var overlay = document.getElementById('saved-panel-overlay');
    if (overlay) overlay.classList.add('open');
    window.print();
    setTimeout(function(){
      document.body.classList.remove('print-saved-mode');
    }, 500);
  }

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
  function openFull(uid) {
    var overlay = document.getElementById('full-overlay');
    var headEl  = document.getElementById('full-headline');
    var metaEl  = document.getElementById('full-meta');
    var bodyEl  = document.getElementById('full-body');
    if (!overlay) return;

    // Source elements
    var srcHead = document.getElementById('hl-'   + uid);
    var srcMeta = document.getElementById('meta-' + uid);
    var srcBody = document.getElementById('body-' + uid);

    headEl.textContent = srcHead ? srcHead.textContent : '';
    metaEl.innerHTML   = srcMeta ? srcMeta.innerHTML   : '';

    if (srcBody) {
      var clone = srcBody.cloneNode(true);
      // Force all study drawers open
      clone.querySelectorAll('.study-drawer').forEach(function(d){ d.style.display = 'block'; });
      // Hide toggle buttons — content is always visible in full view
      clone.querySelectorAll('.study-toggle, .trend-study-toggle').forEach(function(t){ t.style.display = 'none'; });
      bodyEl.innerHTML = '';
      bodyEl.appendChild(clone);
    }

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeFull() {
    var overlay = document.getElementById('full-overlay');
    if (overlay) overlay.classList.remove('open');
    document.body.style.overflow = '';
  }

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
            if (av && user.photoURL) av.src = user.photoURL;
            if (nm) nm.textContent = user.displayName || user.email;
          }
          // Show notes UI
          document.querySelectorAll('.note-login-hint').forEach(function(el){ el.style.display='none'; });
          document.querySelectorAll('.note-textarea').forEach(function(el){ el.style.display='block'; });
          document.querySelectorAll('.note-save-row').forEach(function(el){ el.style.display='flex'; });
          // Load cloud data
          _loadCloudVocab(user.uid);
          _loadCloudNotes(user.uid);
        } else {
          if (loginBtn) loginBtn.style.display = 'flex';
          if (userPill) userPill.style.display = 'none';
          document.querySelectorAll('.note-login-hint').forEach(function(el){ el.style.display=''; });
          document.querySelectorAll('.note-textarea').forEach(function(el){ el.style.display='none'; });
          document.querySelectorAll('.note-save-row').forEach(function(el){ el.style.display='none'; });
        }
      });
    }
    initFirebase();

    window.signInWithGoogle = function() {
      if (!window._fb) return;
      window._fb.auth.signInWithPopup(new firebase.auth.GoogleAuthProvider());
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
          localList.forEach(function(item) {
            document.querySelectorAll('.save-vocab-btn, .save-vocab-btn-sm').forEach(function(b) {
              if ((b.getAttribute('onclick') || '').indexOf(item.phrase.replace(/'/g,"\\'")) !== -1) {
                b.classList.add('saved');
              }
            });
          });
        }).catch(function(){});
    }

    function _loadCloudNotes(uid) {
      window._fb.db.collection('users').doc(uid).collection('notes')
        .get().then(function(snap) {
          snap.forEach(function(doc) {
            var area = document.getElementById('note-area-' + doc.id);
            if (area) area.value = doc.data().text || '';
          });
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

    window.saveNote = function(articleUid) {
      if (!window._fb) return;
      var user = window._fb.auth.currentUser;
      if (!user) return;
      var area   = document.getElementById('note-area-' + articleUid);
      var status = document.getElementById('note-status-' + articleUid);
      if (!area) return;
      window._fb.db.collection('users').doc(user.uid).collection('notes').doc(articleUid)
        .set({ text: area.value, updated: firebase.firestore.FieldValue.serverTimestamp() })
        .then(function() {
          if (status) { status.textContent = 'Saved ✓'; setTimeout(function(){ status.textContent = ''; }, 2000); }
        }).catch(function() {
          if (status) status.textContent = 'Error — try again';
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
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>HKDSE Daily Brief</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600;700&family=Noto+Sans+HK:wght@400;500;700&display=swap" rel="stylesheet" />
  <style>{css}</style>
</head>
<body>

<!-- TOP BAR -->
<header class="topbar">
  <div class="topbar-inner">
    <div class="logo">
      <div class="logo-mark">📰</div>
      <span class="logo-name">HKDSE Daily</span>
    </div>
    <nav class="topbar-nav">
      <button class="nav-tab active" data-cat="all" onclick="filterCards('all',this)">Today's Brief</button>
      <button class="nav-tab" data-cat="tech" onclick="filterCards('tech',this)">Technology</button>
      <button class="nav-tab" data-cat="school" onclick="filterCards('school',this)">School Life</button>
      <button class="nav-tab" data-cat="env" onclick="filterCards('env',this)">Environment</button>
      <button class="nav-tab" data-cat="hk" onclick="filterCards('hk',this)">HK Culture</button>
      <button class="nav-tab" data-cat="pop" onclick="filterCards('pop',this)">Pop Culture</button>
      <button class="nav-tab" data-cat="social" onclick="filterCards('social',this)">Social</button>
      <button class="nav-tab" data-cat="econ" onclick="filterCards('econ',this)">Economy</button>
      <button class="nav-tab" data-cat="health" onclick="filterCards('health',this)">Health</button>
      <button class="nav-tab" data-cat="global" onclick="filterCards('global',this)">Global</button>
    </nav>
    <div class="topbar-right">
      <div class="topbar-date">
        <strong id="today-date">Loading…</strong>
        每日英語精華
      </div>
      <button id="auth-login-btn" class="auth-login-btn" onclick="signInWithGoogle()" title="Sign in to sync vocab & notes across devices">
        <svg width="16" height="16" viewBox="0 0 18 18" fill="none"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#fff"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#fff" opacity=".85"/><path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#fff" opacity=".7"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#fff" opacity=".55"/></svg>
        Sign in
      </button>
      <div id="auth-user-pill" class="auth-user-pill" onclick="signOutGoogle()" title="Click to sign out">
        <img class="auth-avatar" src="" alt="avatar" />
        <span class="auth-user-name"></span>
      </div>
      <button class="btn-open-saved" onclick="toggleSavedPanel()" title="My saved vocab list">
        💾 My Vocab <span class="saved-count-badge" id="saved-count-badge"></span>
      </button>
      <button class="btn-print-page" onclick="window.print()" title="Print today's brief">🖨️ Print</button>
    </div>
  </div>
</header>

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

<!-- FULL-SCREEN ARTICLE OVERLAY -->
<div class="full-overlay" id="full-overlay" onclick="if(event.target===this)closeFull()">
  <div class="full-overlay-inner">
    <div class="full-overlay-topbar">
      <button class="full-close-btn" onclick="closeFull()">← Back</button>
    </div>
    <h2 class="full-headline" id="full-headline"></h2>
    <div class="full-meta" id="full-meta"></div>
    <div class="full-body" id="full-body"></div>
  </div>
</div>

<div class="site-body">

  <!-- LEFT SIDEBAR -->
  <aside class="left-sidebar">
    <div class="sidebar-section-label">Topics</div>
    <button class="sidebar-link active" data-cat="all" onclick="filterCards('all',this)"><span class="sl-icon">🏠</span> All Topics</button>
    <button class="sidebar-link" data-cat="tech" onclick="filterCards('tech',this)"><span class="sl-icon">🖥</span> Technology</button>
    <button class="sidebar-link" data-cat="school" onclick="filterCards('school',this)"><span class="sl-icon">📚</span> School Life</button>
    <button class="sidebar-link" data-cat="env" onclick="filterCards('env',this)"><span class="sl-icon">🌿</span> Environment</button>
    <button class="sidebar-link" data-cat="hk" onclick="filterCards('hk',this)"><span class="sl-icon">🏮</span> HK Culture</button>
    <button class="sidebar-link" data-cat="pop" onclick="filterCards('pop',this)"><span class="sl-icon">🎵</span> Pop Culture</button>
    <button class="sidebar-link" data-cat="social" onclick="filterCards('social',this)"><span class="sl-icon">📊</span> Social</button>
    <button class="sidebar-link" data-cat="trends" onclick="filterCards('trends',this)"><span class="sl-icon">📲</span> Social Trends</button>
    <div class="sidebar-divider"></div>
    <button class="sidebar-link" data-cat="econ" onclick="filterCards('econ',this)"><span class="sl-icon">💰</span> Economy</button>
    <button class="sidebar-link" data-cat="health" onclick="filterCards('health',this)"><span class="sl-icon">🏥</span> Health</button>
    <button class="sidebar-link" data-cat="global" onclick="filterCards('global',this)"><span class="sl-icon">🌍</span> Global Affairs</button>
    <button class="sidebar-link" data-cat="urban" onclick="filterCards('urban',this)"><span class="sl-icon">🏗</span> Urban Dev</button>
    <button class="sidebar-link" data-cat="law" onclick="filterCards('law',this)"><span class="sl-icon">⚖️</span> Law & Justice</button>
    <button class="sidebar-link" data-cat="career" onclick="filterCards('career',this)"><span class="sl-icon">🎓</span> Career</button>
    <button class="sidebar-link" data-cat="sports" onclick="filterCards('sports',this)"><span class="sl-icon">🏅</span> Sports</button>
    <button class="sidebar-link" data-cat="arts" onclick="filterCards('arts',this)"><span class="sl-icon">🎨</span> Arts & Media</button>
    <button class="sidebar-link" data-cat="family" onclick="filterCards('family',this)"><span class="sl-icon">👨‍👩‍👧</span> Family</button>
  </aside>

  <!-- MAIN CONTENT -->
  <main class="main-content">
    <div class="main-section-head">
      <h2>Today's News</h2>
      <span class="section-see-all">Updated daily</span>
    </div>
    {hero}
    <div class="articles-grid">
      {articles_grid}
    </div>
    {trends_main}
  </main>

  <!-- RIGHT SIDEBAR -->
  <aside class="right-sidebar">
    <div class="sidebar-widget-head">
      <h3>Trending on Social</h3>
      <span class="sidebar-see-all">📲</span>
    </div>
    {trends_sidebar}
    {countdown_sidebar}
  </aside>

</div><!-- .site-body -->

<footer>
  HKDSE Daily Brief · 每日英語精華 &nbsp;|&nbsp; For educational use only &nbsp;·&nbsp;
  Hover <strong style="color:var(--accent)">blue words</strong> for definitions · Click 🔊 to hear pronunciation
</footer>

<!-- Firebase SDKs (compat version — works without bundler) -->
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>
<script>{js}</script>
</body>
</html>"""


def build_page(data: dict) -> str:
    """Assemble the complete HTML page from generated data."""
    # Resolve exam date
    exam_date, _, is_estimated = get_next_exam_date()
    raw_exam = data.get("exam_date")
    if raw_exam and raw_exam != "null":
        try:
            found = date.fromisoformat(raw_exam)
            if found > date.today():
                exam_date    = found
                is_estimated = False
        except ValueError:
            pass

    # Fetch article images
    articles = data.get("articles", [])
    article_images: list[str | None] = []
    for a in articles:
        url = a.get("source_url", "")
        img = None
        if url.startswith("http"):
            print(f"  📷 Fetching image: {url[:60]}…")
            img = fetch_og_image(url)
            print(f"     {'✓ ' + img[:65] if img else '(none)'}")
        article_images.append(img)

    # Hero = first article
    if articles:
        hero_html = build_hero_html(articles[0], article_images[0], "a0")
        grid_html = "".join(
            build_article_card_html(a, article_images[i+1], f"a{i+1}")
            for i, a in enumerate(articles[1:])
        )
    else:
        hero_html = ""
        grid_html = ""

    raw_trends = data.get("trends", [])

    # Trends in right sidebar
    trends_html = "".join(
        build_trend_sidebar_html(t, i)
        for i, t in enumerate(raw_trends)
    )

    # Trends in main feed
    trends_main_html = build_trend_main_html(raw_trends)

    # Countdown widget
    countdown_html = build_countdown_widget_html(exam_date, is_estimated)

    return HTML_TEMPLATE.format(
        css=CSS,
        js=JS,
        hero=hero_html,
        articles_grid=grid_html,
        trends_main=trends_main_html,
        trends_sidebar=trends_html,
        countdown_sidebar=countdown_html,
    )


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
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
