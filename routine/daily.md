# HKDSE Daily Brief — daily instructions

(Setup is already done: you are in /home/user/hkdse-daily with push access.)

STEP 2 — CHOOSE TODAY'S 4 TOPICS (fill the emptiest library sections)
Run:
  python3 - <<'PY'
import json, collections, datetime
arc = json.load(open('archive.json', encoding='utf-8'))
cats = ['tech','school','env','hk','pop','social','econ','health','global','urban','law','career','sports','arts','family']
total = collections.Counter(a['category'].split()[0] for a in arc['articles'])
week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
recent = collections.Counter(a['category'].split()[0] for a in arc['articles'] if a.get('date','') >= week_ago)
order = sorted(cats, key=lambda c: (recent[c], total[c]))
print('Library totals:', dict(total))
print('Last 7 days:', dict(recent))
print('Priority order (emptiest first):', order)
PY
Pick the first 4 categories in the priority order that have real news from the past 48 hours. Skip a category only if you truly cannot find a real, recent Hong Kong-relevant story.

STEP 3 — FIND THE NEWS (web_search)
For each chosen category, find one real article published in the past 48 hours from RTHK, The Standard, SCMP, Mingpao English, HKFP or HK01 (translate HK01 from Chinese). Use searches like "Hong Kong <topic> news <month> <year>". Record the exact article URL (source_url) — the article page itself, not a section or search page.
Also find 1 Hong Kong social media trend from the past week (TikTok / Instagram / Threads / Facebook).

STEP 4 — WRITE /home/user/hkdse-daily/data.json
Exact structure (valid JSON, no comments):
{
  "exam_date": null,
  "articles": [
    {
      "source_name": "RTHK",
      "source_url": "https://news.rthk.hk/...",
      "published_date": "30 September 2026",
      "headline": "English headline",
      "category": "sports",
      "summary_html": "<p>...</p><p>...</p><p>...</p>",
      "summary_zh_html": "<p>...</p><p>...</p><p>...</p>",
      "image_scene": "...",
      "cover_text": {"zh_kicker": "...", "zh_title": ["...", "..."], "zh_hl": "...", "zh_sub": "...", "en": "..."},
      "vocab":   [ {"phrase": "...", "zh": "...", "sample": "..."} ],
      "phrases": [ {"en": "...", "zh": "...", "sample": "..."} ]
    }
  ],
  "trends": [
    {
      "platforms": ["tiktok", "ig"],
      "headline": "Emoji + trend headline",
      "summary_html": "<p>...</p>",
      "summary_zh_html": "<p>...</p>",
      "causes": [ {"label": "...", "text": "..."} ]
    }
  ]
}

CONTENT RULES
- summary_html: 250–300 words, 3+ paragraphs, formal HKDSE Paper 2 register. Mark 6–10 key expressions with EXACTLY:
  <span class=\"bw\">phrase<span class=\"tip\"><span class=\"tip-en\">English definition</span><span class=\"tip-zh\">中文釋義</span></span></span>
- summary_zh_html: a COMPLETE, faithful Traditional Chinese (繁體中文, Hong Kong usage) translation of the whole English summary — every paragraph, same paragraph count, wrapped in <p> tags. Not a summary, no Simplified Chinese.
  Matched highlights: wherever the English marks a phrase with <span class="bw">…</span>, wrap the Chinese words that translate THAT phrase in <span class="bwz">…</span>. Same number of marks, in the same order (the 3rd English mark pairs with the 3rd Chinese mark). No tooltip spans inside the Chinese — just <span class="bwz">譯文</span>. The site links each pair so students can see which Chinese words match which English phrase.
- cover_text: the bilingual key message printed on the article's cover image (Hong Kong news Instagram style). Write it like a punchy HK news-post headline:
    {"zh_kicker": "2–6 character tag, e.g. 白石角站",
     "zh_title": ["line 1, ≤8 characters", "line 2, ≤8 characters"],
     "zh_hl": "the most striking part of zh_title (a number, a twist, a key word) — must appear exactly inside one title line",
     "zh_sub": "one supporting line, ≤14 characters, e.g. 發展局：區內配套不足",
     "en": "English key message, 6–10 words, plain and factual"}
  Traditional Chinese only (Hong Kong usage). Accurate to the article — no exaggeration or clickbait that the story does not support.
- image_scene: 1–2 sentences (40–70 words) describing LITERALLY what the cover picture should show for THIS story, so a reader understands the news at a glance: the real Hong Kong place or venue, what is happening, who is involved (as anonymous people — no named or recognisable individuals) and the key objects. Concrete and visual, not symbolic. Example for a hospital opening: "Elderly residents with walking sticks waiting at a bus stop outside a huge brand-new public hospital in Kai Tak, a green minibus pulling up; Victoria Harbour behind." For sad or sensitive stories (deaths, abuse, arrests, self-harm) describe a calm, respectful setting related to the story and never show harm, injuries, victims or children in distress. No text, signs or logos in the scene.
- vocab: 10–12 items, specific to THIS story's subject matter (e.g. for a sports story: "podium finish", "grassroots development"). zh = Traditional Chinese only. sample = a full DSE-quality sentence about this topic.
- phrases: 10–15 reusable Paper 2 expressions that fit THIS article's argument and topic — e.g. ways to discuss sports funding, heritage conservation, or AI in the workplace. Each article must teach a DIFFERENT set. Never use generic stock connectives. These are banned: "It is widely argued that", "Critics contend that", "Nevertheless", "By the same token", "play a pivotal role in", "It is widely reported that", "digital literacy", "foster critical thinking".
- Trend causes (DSE writing angles): exactly 4, each from a DIFFERENT analytical lens, chosen to suit this trend. Lenses to choose from: economic impact on local businesses; generational divide; Hong Kong identity and belonging; ethics and responsibility; mental health and wellbeing; government policy and regulation; environmental cost; commercialisation of grassroots culture; heritage vs globalisation; media literacy and misinformation; equity and access; safety and risk; implications for schools and learning; community and social cohesion; privacy and data; long-term sustainability of the trend; a counter-argument that challenges the trend's value. At least one of the 4 must be a counter-argument. Each label must be specific to this trend (e.g. "Cha chaan teng nostalgia as identity", not "Cultural identity"). Each text: 40–60 words, giving an argument a student could build a Paper 2 paragraph around. Never use the labels "Psychological appeal", "Social media influence" or "Consumer culture".
- Escape any double quote inside a JSON string as \" (or use “ ” curly quotes).
- category must be one of: tech/school/env/hk/pop/social/econ/health/global/urban/law/career/sports/arts/family

STEP 5 — QUALITY GATE (must pass before publishing)
  python3 check_data.py data.json
It checks that every item has a full Chinese translation, that no phrase, vocab item or trend angle repeats anything already in the library, and that the minimum counts are met. If it lists problems, rewrite ONLY the flagged items in data.json and run it again. Repeat until it prints "All checks passed". Never publish content that fails this check.

STEP 6 — ADD TO THE LIBRARY AND BUILD
  cp data.json /tmp/today.json
  python3 generate.py --merge data.json
This appends today's content to archive.json (old articles are kept) and rebuilds index.html plus the a/ folder of full article pages.

STEP 7 — PUBLISH
  git add archive.json index.html a/ data.json
  git commit -m "Daily brief: $(TZ='Asia/Hong_Kong' date +'%Y-%m-%d %H:%M HKT')"
  git push origin main
If the push is rejected because the remote changed, do NOT merge archive.json by hand. Instead:
  git fetch origin && git reset --hard origin/main
  cp /tmp/today.json data.json
  python3 generate.py --merge data.json
  git add archive.json index.html a/ data.json && git commit -m "Daily brief: $(TZ='Asia/Hong_Kong' date +'%Y-%m-%d %H:%M HKT')" && git push origin main
Repeat up to 3 times. A GitHub Action then makes AI cover images automatically (never use photos from news sites).

STEP 8 — REPORT
Output: the 4 categories chosen and why, the headlines, the trend and its 4 angle labels, the check_data.py result, and the pushed commit SHA.
