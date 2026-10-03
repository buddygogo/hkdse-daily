# HKDSE library upgrade — backfill instructions

(Setup is already done: you are in /home/user/hkdse-daily with push access.)

  echo '{}' > /tmp/all_patches.json

STEP 2 — LIST WHAT NEEDS WORK
  python3 -c "import json;a=json.load(open('archive.json',encoding='utf-8'));t=[x for x in a['trends'] if x.get('needs_backfill')];r=[x for x in a['articles'] if x.get('needs_backfill')];print(len(t),'trends',len(r),'articles left');[print(x['id'],x.get('category',''),x['headline'][:70]) for x in (t+r)[:20]]"
If nothing is left, print "Backfill complete" and stop.
Take the first 20 items printed (trends come first).

STEP 3 — UPGRADE IN BATCHES OF 5
For each batch of 5 items, read each item's full record from archive.json, then write /home/user/hkdse-daily/patch.json mapping id → the new fields:

For an ARTICLE (id starts with "a"):
  "summary_zh_html": COMPLETE faithful Traditional Chinese (繁體中文, Hong Kong usage) translation of the item's existing summary_html — every paragraph, same paragraph count, <p> tags, no Simplified Chinese.
    Matched highlights: wherever the English marks a phrase with <span class="bw">…</span>, wrap the Chinese words that translate THAT phrase in <span class="bwz">…</span> — same number of marks, same order. No tooltip spans in the Chinese.
  "phrases": 10–15 NEW reusable Paper 2 expressions specific to this article's topic and argument, {"en","zh","sample"}, sample = a full DSE-quality sentence on this topic. Banned: "It is widely argued that", "Critics contend that", "Nevertheless", "By the same token", "play a pivotal role in", "It is widely reported that", "digital literacy", "foster critical thinking".
  "cover_text": bilingual key message for the cover image —
    {"zh_kicker": "2–6 character tag", "zh_title": ["≤8 chars", "≤8 chars"], "zh_hl": "striking part of a title line (must appear inside it)",
     "zh_sub": "≤14 character supporting line", "en": "6–10 word English key message"}. Traditional Chinese, accurate to the article, no clickbait.
  "vocab": only include this key if check_data.py flags a vocab item — then supply a full replacement list of 10–12 topic-specific items.

For a TREND (id starts with "t"):
  "summary_zh_html": complete Traditional Chinese translation of summary_html, with <span class="bwz">…</span> around the Chinese for each English <span class="bw"> phrase (same count, same order).
  "causes": exactly 4 DSE writing angles, each from a DIFFERENT analytical lens suited to this trend — choose from: economic impact on local businesses; generational divide; Hong Kong identity and belonging; ethics and responsibility; mental health and wellbeing; government policy and regulation; environmental cost; commercialisation of grassroots culture; heritage vs globalisation; media literacy and misinformation; equity and access; safety and risk; implications for schools; community and social cohesion; privacy and data; long-term sustainability; a counter-argument challenging the trend's value. At least one must be a counter-argument. Labels specific to this trend (not generic), each text 40–60 words. Never use "Psychological appeal", "Social media influence" or "Consumer culture".

Example patch.json shape:
  {"t1a2b3c4d": {"summary_zh_html": "<p>…</p>", "causes": [{"label": "…", "text": "…"}]},
   "a9f8e7d6c": {"summary_zh_html": "<p>…</p><p>…</p>", "phrases": [{"en": "…", "zh": "…", "sample": "…"}]}}
Escape double quotes inside JSON strings as \" or use “ ”.

Then run:
  python3 check_data.py --backfill patch.json
Fix only what it flags and re-run until "All checks passed". Then apply:
  python3 generate.py --backfill patch.json
  python3 -c "import json;a=json.load(open('/tmp/all_patches.json'));a.update(json.load(open('patch.json',encoding='utf-8')));json.dump(a,open('/tmp/all_patches.json','w'),ensure_ascii=False)"
Move on to the next batch of 5.

STEP 4 — PUBLISH (after all batches)
  git add archive.json index.html a/
  git commit -m "Library upgrade: Chinese translations and unique phrases"
  git push origin main
If the push is rejected because the remote changed, do NOT merge archive.json by hand. Instead:
  git fetch origin && git reset --hard origin/main
  python3 generate.py --backfill /tmp/all_patches.json
  git add archive.json index.html a/ && git commit -m "Library upgrade: Chinese translations and unique phrases" && git push origin main
Repeat up to 3 times.

STEP 5 — REPORT
How many items were upgraded, how many remain, and the pushed commit SHA.
