# HKDSE Daily Brief — Claude Code Instructions

This project generates a daily English learning website for Hong Kong secondary school
students preparing for HKDSE Paper 2 (Writing).

## What this project does

Running `python generate.py` will:

1. Search the web for 2–3 current news articles relevant to HKDSE writing topics
2. Search for 1–2 trending social media topics popular among HK youth
3. Search for the upcoming HKDSE English Paper 2 exam date
4. Fetch a cover photo from each article
5. Generate a complete `index.html` with:
   - HKDSE-style news summaries (formal register, hedging language, discourse markers)
   - Hover tooltips on key vocabulary (English definition + Cantonese translation)
   - 🔊 speak buttons for every word/phrase (Web Speech API, no external service)
   - 5 vocab items per article with Cantonese translation and sample sentences
   - A quick-reference phrase/Cantonese table per article
   - Social trend summaries with analysed causes (HKDSE writing angles)
   - HKDSE English Paper 2 countdown timer at the bottom (auto-updates daily)

## Setup

```bash
pip install anthropic requests beautifulsoup4
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running

```bash
python generate.py
```

Then open `index.html` in your browser.

## Deploying to GitHub Pages (public URL for students)

1. Create a GitHub repository (public)
2. Push this project to it
3. Add your `ANTHROPIC_API_KEY` as a GitHub Secret:
   - Repo → Settings → Secrets and variables → Actions → New secret
   - Name: `ANTHROPIC_API_KEY`
4. Enable GitHub Pages:
   - Repo → Settings → Pages → Source: GitHub Actions
5. The workflow in `.github/workflows/daily.yml` will run daily at 2 PM HKT,
   regenerate `index.html`, and deploy it automatically.
6. Your public URL will be: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME`

## Updating HKDSE exam dates

When HKEAA publishes the exam timetable (usually October–November), update
`KNOWN_EXAM_DATES` in `generate.py`:

```python
KNOWN_EXAM_DATES: dict[int, date] = {
    2025: date(2025, 4, 24),
    2026: date(2026, 4, 23),
    2027: date(2027, 4, 22),  # ← update this each year
}
```

The script also searches for the date automatically on each run.

## Using with Claude Code CLI

```bash
claude -p "Run python generate.py to regenerate today's HKDSE Daily Brief"
```

Or just run `python generate.py` directly.

## File structure

```
.
├── generate.py                    ← main script (run this)
├── index.html                     ← generated output (deploy this)
├── CLAUDE.md                      ← this file
├── requirements.txt               ← Python dependencies
└── .github/
    └── workflows/
        └── daily.yml              ← GitHub Actions: runs daily at 2PM HKT
```

## HKDSE topics covered

### Original topics
- 🖥 Technology — AI, social media, digital life
- 📚 School Life — education policy, student wellbeing, learning
- 🌿 Environment — climate, pollution, sustainability, policy
- 🏮 HK Culture & Tradition — heritage, festivals, identity, food culture
- 🎵 Pop Culture — K-pop, C-pop, entertainment, gaming, fashion
- 📊 Social Trends & Issues — mental health, youth, inequality, consumer behaviour

### Additional topics (added for broader Paper 2 coverage)
- 💰 Economy & Finance — inflation, cost of living, job market, business trends
- 🏥 Health & Medicine — public health, mental health, medical innovation, wellbeing
- 🌍 Global Affairs & Geopolitics — international relations, trade, diplomacy
- 🏗 Urban Development & Housing — smart city, infrastructure, transport, property
- ⚖️ Law, Justice & Ethics — crime trends, legal reform, social justice, rights
- 🎓 Career & Future of Work — employment, skills gap, AI in workplace, entrepreneurship
- 🏅 Sports & Fitness — HK athletes, youth sport, wellness trends
- 🎨 Arts, Media & Journalism — film, music, publishing, press freedom
- 👨‍👩‍👧 Family & Society — elderly care, parenting, gender, community

## Category codes (used in `generate.py`)

| Code     | Topic                    |
|----------|--------------------------|
| tech     | Technology               |
| school   | School Life              |
| env      | Environment              |
| hk       | HK Culture               |
| pop      | Pop Culture              |
| social   | Social Trends            |
| econ     | Economy & Finance        |
| health   | Health & Medicine        |
| global   | Global Affairs           |
| urban    | Urban Development        |
| law      | Law & Justice            |
| career   | Career & Future of Work  |
| sports   | Sports & Fitness         |
| arts     | Arts & Media             |
| family   | Family & Society         |
