# Tech Shorts Autopilot: Design

Status: draft v2, waiting for owner approval
Date: 2026-11-14, revised 2026-11-19
Changes in v2: trending-first content twice a day; 7 platforms (core 4 + Threads + LinkedIn + X); character
"Byte v3" and its voice are built and approved; rendering stack is cairosvg (built), not skia.

---

## 1. Intent

The owner wants a **standalone system that earns money without them doing anything day to day.** Twice a day it
finds what is new and trending in **software engineering and AI**, turns it into a short video hosted by the
original mascot **Byte** (a kawaii developer squirrel), posts it to 7 platforms, keeps the accounts connected,
shows stats on a dashboard, and earns ad / creator revenue. Running costs must be as close to $0 as possible.

After the one-time setup, **the only thing the owner provides is account credentials** (the logins and app keys
in §9). Everything else is automatic.

Success means: the system posts 2 videos a day for months with no intervention, keeps viewers up to date with
what changed in software that day, passes platform monetization reviews, and the owner only opens the dashboard
when they want to.

### Goals
- Fully automatic: trend scan, script, fact-check, video, publish, analytics.
- One brand, one niche (**software engineering & AI news, English**), cross-posted to 7 platforms.
- Two daily shows (§5.2): morning **"Dev News in 60s"** and evening **"Deep Byte"**.
- An original recurring mascot that is the channel's identity (built: §5.6).
- Web dashboard: accounts and token health, video queue and history, stats, settings.
- Running costs about $3–5/month (Claude API + X API usage; everything else free tier or open source).
- Monetization through platform ad revenue with the fewest human steps (YouTube Partner Program first).

### Non-goals (v1)
- Reddit: API access now needs approval, bot accounts are labelled, automated posts are routinely removed, and
  it pays nothing. Dropped (can be added later as an adapter if the owner wants).
- Several niches or channels (the niche is config, so a second one is a config change, not code).
- Long-form videos (phase 2: weekly compilation of the week's news).
- Affiliate marketing (description slot exists, off by default).
- Replying to comments or community management (phase 2: pinned comment with sources only).

### Anti-goals (a failure even if it "works")
- Content that platforms classify as **mass-produced / inauthentic / reused**: demonetization. Quality and
  variety beat volume.
- Wrong facts presented as news. Every claim is fact-checked against its source; uncertain items are dropped.
- Re-uploading other people's footage, screenshots of paywalled articles, or reading articles verbatim. Byte
  explains in its own words, cites sources in the description.
- Medical, financial or legal advice; defamatory claims about real people or companies; politics.
- Unofficial automation (browser bots, scraping logins). **Official APIs only**, so accounts are not banned.
- Silent failure: the system tells the owner (Telegram) when it stops posting or a token is about to expire.

---

## 2. Constraints

- **Host:** Oracle Cloud Always Free, ARM64 (Ampere A1, up to 4 OCPU / 24 GB RAM), Ubuntu, Docker. Everything
  runs on linux/arm64. No headless Chrome.
- **Budget:** about $0 infrastructure; Claude API with a hard monthly cap (default $6); X API credits with a
  hard monthly cap (default $2).
- **Freshness:** a news video must be published within ~4 h of the scan that found the story. News videos are
  never buffered for later days; the buffer (§4) holds only evergreen fallbacks.
- **Steps only a human can do** (one-time, about 3–5 hours spread over the first weeks): see §9. The dashboard
  turns each into a guided step, and the system keeps working (posting privately or skipping a platform) while
  an approval is pending.
- **Platform rules built in from day one** (verify each against current docs during the build, §12):
  - **YouTube:** an unverified API project's uploads are locked to private until it passes the YouTube API
    compliance audit. The OAuth consent screen must be **published to "In production"** ("Testing" refresh
    tokens expire after 7 days). Upload quota about 6 videos/day by default. Set
    `status.containsSyntheticMedia = true` on every upload.
  - **TikTok:** unaudited Content Posting API clients can post only as `SELF_ONLY`. Apply for the audit early;
    the adapter detects the audited state and switches to public. Access token 24 h, refresh token 365 days.
    Creator Rewards needs videos over 1 minute and an eligible country.
  - **Instagram / Facebook:** Instagram Professional account linked to a Facebook Page; Meta app in development
    mode with the owner holding a role on it (own-account use). Resumable upload, no public video URL needed.
  - **Threads:** Threads API (Meta app, `threads_basic` + `threads_content_publish`). Video posts need a public
    video URL (served by the app through Tailscale Funnel for the minutes of the upload, or a signed Object
    Storage URL). 250 posts / 24 h limit. Long-lived token 60 days, refreshable.
  - **LinkedIn:** "Share on LinkedIn" product (self-serve, `w_member_social`) posting to the owner's **personal
    profile** via the Posts API + Videos API. Posting to a company page needs the Community Management API
    (application + review): optional, later. Token 60 days; refresh tokens only for approved partners, so the
    owner re-connects about every 2 months (Telegram reminder 7 days before).
  - **X:** pay-per-use API (since Feb 2026): about $0.015 per post (more if the post contains a URL, so the
    link goes in a reply or not at all). Chunked media upload for video (up to 140 s). OAuth 2.0 with PKCE,
    refresh tokens. Owner buys a small credit balance once.
  - TikTok, Meta and LinkedIn apps need a privacy-policy / terms URL: a static page on **GitHub Pages** ($0).
- **AI disclosure:** set synthetic-content flags wherever an API offers them (YouTube
  `containsSyntheticMedia`, TikTok AIGC flag, Meta "AI info" label if exposed). "AI-assisted, sources below"
  line in every description.

---

## 3. Approaches considered

### 3.1 System shape. **Chosen: one Python application**
| Option | Trade-off |
|---|---|
| **A. One Python app (chosen)**: scheduler, all stages, FastAPI dashboard, SQLite, Docker Compose | Fewest moving parts, fully unit-testable, buildable and verifiable by an AI coding session. Prompts and schedules live in YAML config / dashboard. |
| B. n8n orchestrator + Python render worker | Visual editor, but hard to test automatically, still needs a stats dashboard, adds Postgres and a service. |
| C. Hosted no-code (Make/Zapier) + rendering API | Monthly and per-render fees. Breaks the $0 goal. |

### 3.2 Content strategy. **Chosen: trending-first, two shows a day, evergreen as fallback**
| Option | Trade-off |
|---|---|
| **Trending-first (chosen)**: morning top-3 news + evening deep dive on the day's biggest story | What the owner asked for; news is a strong reason to follow ("keeps me updated"); varied by nature, which protects against "repetitive content". Needs strict fact-checking and fast publishing. |
| Evergreen explainers only | Easier, ages well, but no reason to come back daily; crowded niche. Kept as a fallback when the news is thin. |
| Pure aggregation (headline cards, no host) | Cheapest, but looks mass-produced; demonetization risk. Rejected. |

### 3.3 Character. **Chosen and built: original squirrel drawn in code (parametric SVG rig)**
$0, perfectly consistent, versioned in git. AI image / video generation rejected (drift, cost, generic look).

### 3.4 Character role. **Chosen: host + visuals**
Byte is full-frame for the hook (0–3 s) and the sign-off. During the story it shrinks to a corner (about 30 %
width) and reacts (points, surprised, thinking, sips coffee) while headlines, code, diagrams and release notes
fill the screen.

### 3.5 Rendering stack. **Chosen and built: SVG per frame → cairosvg → FFmpeg**
Each frame is a pure function of time producing an SVG, rasterized by cairosvg and piped to FFmpeg
(1080×1920, 30 fps, ~0.1 s/frame on the dev box). Remotion and Manim were rejected (headless Chrome / heavy).

### 3.6 Model use (cost-driven)
- Script writing: `claude-sonnet-5-5`, about $0.02–0.04 per video.
- Story clustering and ranking, metadata, policy filter, frame QA (vision): `claude-haiku-5-5`, well under $0.01.
- Fact-check: `claude-sonnet-5-5` with server-side web search (`max_uses` 4) plus the fetched source pages.
- All model ids in config; owner can switch scripts to `claude-opus-5-5` (about 2× script cost).
- Official `anthropic` SDK, structured outputs for every JSON stage, prompt caching on the persona prompt.

---

## 4. Architecture

```
┌──────────────────────── Oracle ARM VM (Docker Compose) ────────────────────────┐
│ app (Python 3.12)                                                              │
│  scheduler (APScheduler): scans 05:30 and 14:30 (owner's timezone, config)    │
│    1 trends     collectors (§5.2) → normalize → cluster same story →          │
│                 score (velocity × reach × relevance) → pick per show (Haiku)  │
│    2 research   fetch source pages (official post / release notes / repo)     │
│    3 script     Sonnet: persona + show format + sources → Script JSON         │
│    4 factcheck  Sonnet + web search → pass / fix / drop (claim by claim)       │
│    5 policy     Haiku: banned topics + claims filter                           │
│    6 voice      Kokoro TTS (local) → warm EQ → wav                             │
│    7 timing     Rhubarb (mouth shapes) + faster-whisper (word timestamps)     │
│    8 assets     headline cards, code cards, diagrams, logos-as-text (no logos)│
│    9 render     SVG frames → cairosvg → FFmpeg → 1080×1920 MP4 + cover        │
│   10 qa         ffprobe, loudness, duration, captions, Haiku vision on frames  │
│   11 publish    adapters: YouTube · TikTok · Instagram · Facebook ·            │
│                 Threads · LinkedIn · X  (each isolated)                        │
│   12 analytics  daily stats pull → DB → topic / format / source scoring        │
│  dashboard      FastAPI + Jinja + HTMX + Chart.js                              │
│  notifier       Telegram bot (alerts, daily summary, optional veto window)     │
│ SQLite (WAL) · /data volume: assets, renders (30-day retention), backups       │
└────────────────────────────────────────────────────────────────────────────────┘
Remote access: Tailscale for the dashboard; Tailscale Funnel exposes only the OAuth
callback and short-lived video URLs (Threads) over HTTPS.
```

**Resilience rule:** each stage is idempotent, reads the previous stage's saved output from `/data/jobs/<id>/`,
writes its own, and records status in SQLite. On failure: retry with backoff (3×), then mark `failed`, alert,
continue. A failed stage can be re-run from the dashboard.

**Fallback rule:** if a show's run fails or the news is too thin (no story above the score threshold, or all
stories dropped by fact-check), publish the next **evergreen video from the buffer** (target 3 ready). The
buffer is refilled on quiet days. So a bad scan never means a missed slot.

---

## 5. Components

### 5.1 Channel config (`config/channel.yaml`)
Niche, language, timezone, show schedule (scan and publish times per show and per platform), platforms
enabled, review mode (`off` default | `veto` with N-hour window | `approve`), model ids, monthly LLM and X caps,
source list and weights, banned topics, description templates, hashtag policy. Edited from the dashboard.
Secrets only in `.env` / the encrypted token store.

### 5.2 Trend engine (the core of v2)
**Collectors** (all free and official / public, each a small plugin with its own rate limit and timeout):
| Source | What it gives |
|---|---|
| Hacker News (Firebase API + Algolia search) | top/best stories, points and comments velocity |
| GitHub: trending page + Search API (repos created in last 7 days, sorted by stars) | rising repos, star velocity |
| GitHub releases of a watch-list (config: Python, Node, Rust, Go, TS, React, Kubernetes, Postgres, VS Code, major LLM SDKs…) | notable releases and changelogs |
| Official engineering / AI blogs via RSS (config list: OpenAI, Anthropic, Google, Meta, Microsoft, AWS, GitHub, Vercel, Cloudflare, JetBrains, Mozilla…) | launches and announcements |
| Lobsters, dev.to (public API), InfoQ / The New Stack RSS | developer community signal |
| arXiv cs.AI / cs.LG / cs.SE RSS + Hugging Face trending (papers, models) | notable research and models |
| Subreddit RSS feeds (r/programming, r/MachineLearning…), read-only, if reachable | discussion signal only, never posted to |

**Pipeline:** normalize items (title, url, source, time, engagement) → dedupe by canonical URL → cluster
"same story" across sources (title embeddings-free: Haiku groups candidate titles; cheap, ~50 items) → score:
`velocity (engagement growth per hour) × cross-source count × relevance to software engineering × novelty
(not covered in the last 14 days)` with per-source weights tuned by analytics (§5.12).

**Shows:**
- **Morning, "Dev News in 60s"** (scan 05:30, publish ~07:30): the **top 3** stories of the last 24 h, ~20 s
  each, a closing "one-liner of the day". Fixed recognizable intro sting and structure.
- **Evening, "Deep Byte"** (scan 14:30, publish ~17:30): **one** story explained properly: what happened,
  why it matters, what to do about it (e.g. "upgrade", "try it", "ignore the hype"), with a code or diagram card.
- Both 61–90 s (TikTok's over-1-minute rule; still a YouTube Short).
- Publish times are config, initially aligned to the owner's audience timezone; analytics may suggest shifts.
- **Variety guard:** rotate hook styles and evening formats ("What changed", "X vs Y", "Should you care?",
  "Myth vs fact", "Explain like I'm 5", "One line of code"); never two consecutive videos with the same hook.
- **Evergreen buffer:** `config/backlog.yaml` of explainer topics ("How does HTTPS work?"), used only as fallback.

### 5.3 Research and script writer
- Research: fetch the primary source (official post, release notes, repo README, paper abstract); store
  extracts and URLs. Never rely on a headline alone.
- Script output (structured JSON, schema-validated):
  `show, title, hook_line, beats[{text, expression, pose, action, prop, visual{template, params},
  emphasis_words[]}], sign_off, description, hashtags[], category, est_duration_s, sources[{url, claim_ids}]`
- Persona: Byte is a friendly, slightly nerdy senior dev who explains things over coffee; warm, calm, a little
  playful, never cringe; reading level "smart junior dev"; 150–210 words; hook in the first 2 s; one clear
  takeaway; no "smash that like button" spam. A short consistent sign-off ("That's your byte for today.").

### 5.4 Fact-check and policy
- Sonnet with web search checks every factual claim against the stored sources: `pass | fixed (patched beats) |
  drop`. Version numbers, dates, benchmark numbers and quotes must match a source exactly. One rewrite cycle max,
  then drop the story (morning show: replace with the 4th-ranked story).
- Haiku policy pass: banned topics, real-person accusations, rumours/leaks without an official source, anything
  the fact-check marked unsure.
- Sources go into every description (and as a reply on X / first comment where APIs allow).

### 5.5 Voice (built: `src/autopilot/audio/voice.py`)
- **Kokoro-82M** (Apache-2.0) via `kokoro-onnx` (int8, CPU). Voice **`am_michael` (US), "comfy" tuning**:
  slowed (0.86–0.90), optionally a little lower in pitch (rubberband, formant preserved), low-shelf body boost,
  softened highs, de-esser, gentle compression, very light room, loudness-normalized. Owner picks variant 1, 2
  or 3 from `docs/character/byte_voice_michael_comfy.mp4`; default until then: **2 "comfier"**.
- No squirrel pitch-up (owner rejected it).
- About 8 s of synthesis per 6 s of speech on the dev box; fine for 2 videos a day.
- Optional paid upgrade later: ElevenLabs (same `speak()` interface).

### 5.6 Character rig (built: `src/autopilot/character/`)
- **Byte v3** (approved): chubby fluffy kawaii squirrel, big shiny eyes, tiny smile, blush, puffy cheeks,
  slightly-too-small navy t-shirt with `</>`, cream "dev belly", big curled tail, warm flat style.
- 11 poses, 10 expressions, Rhubarb mouth set X/A–H, 5 outfits (t-shirt, green t-shirt, hoodie, sweater, none),
  4 hats, glasses, props held with 2-bone IK (acorn, coffee, cookie, laptop, sketchbook + pencil).
- Animator: timeline of cues, actions (hop, nod, dance, wave, sip, munch, type, celebrate, wink, pop-in) and
  a mouth track; procedural blink, breathing, tail sway; anticipation and follow-through.
- Intro (1.6 s) and outro (3 s) clips with synthesized SFX (`src/autopilot/audio/sfx.py`, no samples).
- Outfit rotates by show and day (e.g. hoodie + coffee in the morning, t-shirt + laptop in the evening) so
  videos look varied without changing the identity.
- ARM: Rhubarb has no arm64 release; build from source in the Docker image. Fallback: loudness mouth (built).

### 5.7 Visual templates (9:16; safe zones: avoid the bottom 20 % and right 12 %)
1. **Hook card**: big Byte + 3–6-word punchline.
2. **Headline card** (news): source name as text (no logos), headline in Byte's words, date, "1/3" counter.
3. **Code card**: highlighted code (Pygments), typewriter reveal, line highlight on cue.
4. **Diagram**: small JSON DSL → auto layout, animated draw-in, arrows/packets along edges.
5. **Release card**: `v1.2 → v2.0` with 2–3 key changes as bullets.
6. **Comparison split**: X vs Y with checks.
7. **Big number / stat** (only numbers that passed fact-check).
8. **Terminal**: commands typing with output.
Each template is a pure function `(params, t) → SVG layer`, with a snapshot test. No third-party footage or
screenshots in v1 (copyright safety).

### 5.8 Captions, audio, render
- Word-by-word captions from faster-whisper timestamps (fallback: proportional estimate, built), active word
  highlighted, emphasis words coloured.
- Background music: synthesized in code (soft lo-fi loop per show, built from the SFX engine) or CC0 loops with
  licence files; ducked −18 dB under voice. SFX on transitions (built).
- Render: 1080×1920, 30 fps, H.264 High, CRF ~20, AAC 192 k, `+faststart`; cover frame. Target < 8 min on
  4 ARM cores for 90 s.

### 5.9 Automated QA gate (replaces human review)
Fail → re-render once → else mark failed, alert, use the evergreen fallback:
- ffprobe: resolution, fps, duration 61–90 s, audio present, size limits per platform.
- Loudness −14 ±2 LUFS, no silence over 1.2 s.
- Caption coverage ≥ 95 % of spoken words; no text outside safe zones (checked at layout time).
- Haiku vision on 6 sampled frames: broken / overlapping / cut-off text, empty frame, glitch → pass/fail.

### 5.10 Publishers (common interface `publish(video, metadata) → PostResult`)
| Platform | API and method | Notes |
|---|---|---|
| YouTube Shorts | Data API v3 resumable upload | `categoryId 28`, `containsSyntheticMedia=true`, private until audit |
| TikTok | Content Posting API, Direct Post, FILE_UPLOAD chunked | `creator_info` first; `SELF_ONLY` until audit; AIGC flag |
| Instagram Reels | Graph API Reels container (resumable) → poll → publish | `share_to_feed=true` |
| Facebook Reels | Page video_reels API (resumable) | Page token from the same Meta app |
| Threads | Threads API: media container (VIDEO, `video_url`) → poll → publish | short-lived public URL via Funnel |
| LinkedIn | Videos API (initialize, upload parts, finalize) → Posts API | personal profile; `w_member_social` |
| X | media upload (chunked INIT/APPEND/FINALIZE/STATUS) → create post | no URL in the main post (cost); sources in a reply only if budget allows |
- Per-platform captions/titles from the script metadata (length limits, hashtag style per platform).
- Staggered by ~10–20 min; each failure isolated.
- Every adapter has a dry-run mode and a contract test against recorded API responses.

### 5.11 Accounts and tokens
- Dashboard "Accounts" page: Connect button per platform (OAuth), status (connected, expires, audited, quota /
  credits left), Reconnect button, and a checklist of what each platform still needs from the owner.
- Tokens encrypted at rest (Fernet key in `.env`). Background refresh job; Telegram alert 7 days before any
  non-refreshable expiry (LinkedIn, Threads if not refreshed) and on any `invalid_grant`.

### 5.12 Analytics and feedback loop
- Daily pull: YouTube Data + Analytics APIs (views, average view duration, subscribers, estimated revenue);
  TikTok `video.list`; Instagram, Facebook and Threads insights; LinkedIn post stats (where the product allows);
  X post metrics (counts against credits; daily, only last 7 days of posts).
- Scores per show, story category, source, format, hook style, outfit (views at 48 h, normalized per platform).
  They feed source weights, story ranking and format rotation (bounded so variety is kept).
- **Monetization tracker:** YouTube (1,000 subs + 10 M Shorts views / 90 days), TikTok (10 k followers),
  Facebook (content monetization eligibility), X (Premium + 500 verified followers + 5 M impressions / 3 months);
  Telegram alert when a threshold is reached.

### 5.13 Dashboard pages
Overview (totals, 30-day charts per platform, posting streak, spend vs caps, monetization progress) · Today
(scanned stories, scores, which were picked or dropped and why) · Videos (queue and history, per-stage and
per-platform status, inline player, retry/skip/delete) · Accounts · Sources (enable, weights) · Settings · Logs.
Login: single admin password (argon2 hash) + reachable only over Tailscale.

### 5.14 Notifications (Telegram)
Daily summary (posted, top story, views, spend). Alerts: a show missed, buffer empty, token expiring/invalid,
quota or credits low, upload rejected/removed, budget cap reached, disk > 80 %. Optional veto mode: preview sent,
publish after N minutes unless ❌ (short window, because news is time-sensitive).

### 5.15 Operations
- Docker Compose: `app` (`restart: unless-stopped`). Kokoro runs in-process.
- Daily backup of SQLite + config to Oracle Object Storage (Always Free) or a private GitHub repo. Renders
  deleted after 30 days.
- Budget guard: per-call accounting from `response.usage` and X credit usage; stop the stage when a cap is hit
  (X is skipped, other platforms continue), alert.
- Owner upgrades Oracle to Pay-As-You-Go (stays $0) to avoid idle reclamation.
- `./install.sh`: Docker, compose up, key generation, prints the dashboard URL and the setup checklist.

---

## 6. Monetization (fewest human steps)
1. **YouTube Partner Program** (primary): Shorts revenue share; owner applies once (AdSense, tax form).
2. **Facebook content monetization**: one-time opt-in if offered in the owner's country.
3. **TikTok Creator Rewards**: if the owner's country is eligible; videos are already over 60 s.
4. **X creator revenue sharing**: needs X Premium (~$8/month) and the thresholds above. Owner decides when the
   dashboard shows it is close; until then X is for reach only.
5. Instagram, Threads, LinkedIn: no general ad share; used for audience growth and credibility (LinkedIn is a
   good fit for software-engineering news).
6. Phase 2: weekly long-form compilation on YouTube (higher revenue per view), optional affiliate slot.

## 7. Costs (2 videos/day ≈ 60 videos/month)
| Item | $/month |
|---|---|
| Oracle VM, Object Storage, Tailscale, GitHub Pages, Telegram, all OSS, all other platform APIs | 0 |
| Claude: scripts (Sonnet) ~$0.03 × 60 | ~1.80 |
| Claude: fact-check web search (~4 searches × $0.01) × 60 | ~2.40 |
| Claude: Haiku tasks (clustering, ranking, policy, QA vision) | < 0.50 |
| X API: ~60 posts × ~$0.015 + metrics reads | ~1.00 |
| **Total** | **~$4–6** (hard caps: Claude $6, X $2) |
Optional: X Premium (~$8, only to earn on X), ElevenLabs voice (~$22), Opus scripts (+~$2).

## 8. Milestones (each ends with a runnable, verified result)
- **M0 Setup kit**: repo skeleton, Docker, config schema, install script, GitHub Pages privacy page, setup guide
  (§9). *Owner starts the YouTube and TikTok audits now; they take the longest.*
- **M1 Character** ✅ done: rig, wardrobe, props, actions, intro/outro, SFX, voice candidates.
- **M2 Video from a hand-written script**: voice + lip-sync + captions talking demo, templates (§5.7), music,
  render, QA. **Owner quality checkpoint.**
- **M3 Trend engine + content brain**: collectors, clustering, scoring, both shows, research, script, fact-check,
  policy, budget guard, evergreen buffer. Runs twice daily producing finished videos (not yet published).
- **M4 Publishing**: YouTube → Instagram + Facebook → Threads → LinkedIn → X → TikTok. Token management,
  privacy auto-switch, dry-run mode.
- **M5 Dashboard + Telegram**.
- **M6 Analytics loop + monetization tracker**, backups, 7-day unattended soak test on the VM.

## 9. One-time human checklist (credentials and approvals only)
| # | Platform | What the owner does once | What gets pasted / connected |
|---|---|---|---|
| 1 | Oracle Cloud | Create account, ARM VM (Ubuntu 24.04), upgrade to Pay-As-You-Go, run `install.sh` | SSH access only |
| 2 | Tailscale | Install on the VM and phone/PC | login |
| 3 | Anthropic | API key with a spend limit | `ANTHROPIC_API_KEY` |
| 4 | Telegram | Create a bot with BotFather, send it /start | bot token (chat id auto-detected) |
| 5 | YouTube | Google account + brand channel → Cloud project → enable Data + Analytics APIs → OAuth client → consent screen **In production** → Connect → submit API audit | client id/secret, then OAuth in dashboard |
| 6 | TikTok | Account → TikTok for Developers app (Login Kit + Content Posting, Direct Post) → privacy URL → Connect → submit audit | client key/secret, OAuth |
| 7 | Instagram + Facebook | Facebook Page + Instagram Professional account linked to it → Meta developer app (owner as admin) | app id/secret, OAuth |
| 8 | Threads | Threads profile (from the same Instagram) → add the Threads use case to the Meta app | OAuth |
| 9 | LinkedIn | LinkedIn developer app with "Share on LinkedIn" + "Sign In with LinkedIn" → Connect (re-connect every ~60 days when reminded) | client id/secret, OAuth |
| 10 | X | Developer account → app with OAuth 2.0 → buy a small credit balance (~$5 lasts months) → Connect | client id/secret, OAuth |
| 11 | Later | When the dashboard says eligible: YouTube Partner Program (+ AdSense), TikTok / Facebook / X programs | — |

## 10. Risks
| Risk | Mitigation |
|---|---|
| Wrong facts in a news video | Primary-source research, claim-by-claim web fact-check, drop on uncertainty, sources in description. |
| Demonetization for repetitive/AI content | Original mascot, news is naturally varied, format/outfit rotation, AI labels, no reuse. |
| Thin news day / failed scan | Evergreen buffer fallback; morning show can drop to 2 stories. |
| Audits rejected or slow | Started in M0; private posting keeps it exercised; Meta, Threads, LinkedIn, X can be public from day one. |
| Token expiry stops posting silently | Production consent screen, refresh jobs, early reminders (LinkedIn every ~60 days). |
| X pricing changes | Hard credit cap; X adapter is optional and skipped when the cap is reached. |
| Source sites change / block | Each collector isolated with health checks; dashboard shows source health. |
| ARM build issues (Rhubarb, Kokoro, faster-whisper) | Fallbacks built (loudness mouth, estimated timings); verify on arm64 in CI with buildx. |
| Oracle reclaims the VM | Pay-As-You-Go; daily off-box backups; `install.sh` restore path. |
| LLM cost runaway | Hard monthly cap, per-call accounting. |

## 11. Left to the builder
Exact library versions; clustering prompt and score weights (start simple, tune with analytics); diagram
layout algorithm; prompt wording (iterate with sample outputs); SQLite schema; exact RSS / watch-list entries;
dashboard styling.

## 12. Verify during build (claims from research to confirm against current docs)
- X: current per-post price, media upload endpoint version, credit purchase flow, metrics read cost.
- Threads: video `video_url` requirements and whether a resumable/direct upload exists now.
- LinkedIn: self-serve video posting to a personal profile with `w_member_social`; token lifetime.
- Meta: own-account publishing in dev mode without App Review; resumable upload for IG and FB Reels.
- TikTok: AIGC flag field name on Direct Post; token lifetimes.
- YouTube: Shorts classification of 61–90 s vertical API uploads.
- Rhubarb source build and faster-whisper model download on arm64 (Hugging Face CDN reachable from the VM).
