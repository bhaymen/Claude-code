# Tech Shorts Autopilot: Design

Status: draft, waiting for owner approval
Date: 2026-11-14
Earlier brainstorming: session "Automated shorts monetization strategy" (2026-11-10) and this one.

---

## 1. Intent

The owner wants a **standalone system that earns money without them doing anything day to day.** It invents
AI & tech explainer Shorts, renders them with an original mascot (a cute squirrel with glasses), posts them to
YouTube Shorts, TikTok, Instagram Reels and Facebook Reels, keeps the accounts connected, shows stats on a
dashboard, and earns ad revenue. Running costs must be as close to $0 as possible.

Success means: after a one-time setup of a few hours, the system posts 1–2 good videos a day for months with no
intervention, passes platform monetization reviews, and the owner only opens the dashboard when they want to.

### Goals
- Fully automatic, from topic to published video to analytics.
- One brand, one niche (**AI & Tech**, English, 60–90 s), cross-posted to 4 platforms.
- An original recurring mascot that is the channel's identity and drives the script voice.
- Web dashboard: accounts and token health, video queue and history, stats, settings.
- Running costs about $1–4/month (only Claude API usage is paid; everything else is free tier or open source).
- Monetization through platform ad revenue with the fewest human steps (YouTube Partner Program first).

### Non-goals (v1)
- Several niches or channels (the niche is config, so a second one is a later config change, not code).
- Long-form videos (phase 2: compilations of top Shorts).
- Affiliate marketing (a slot in the description template exists, off by default).
- X/Twitter (its API is paid; dropped).
- Replying to comments or community management.

### Anti-goals (a failure even if it "works")
- Content that platforms classify as **mass-produced / inauthentic / reused**. That means demonetization, so
  quality and variety beat volume.
- Copying a movie character. The squirrel must be original (copyright claims and strikes).
- Medical, financial or legal advice, or defamatory claims about real people or companies.
- Unofficial automation (browser bots, scraping logins). **Official APIs only**, so accounts are not banned.
- Silent failure: the system must tell the owner (Telegram) when it stops posting or a token is about to expire.

---

## 2. Constraints

- **Host:** Oracle Cloud Always Free, ARM64 (Ampere A1, up to 4 OCPU / 24 GB RAM), Ubuntu, Docker. Everything
  must run on linux/arm64. Avoid headless Chrome rendering.
- **Budget:** about $0 infrastructure; Claude API with a hard monthly spend cap set in config (default $5).
- **Steps only a human can do** (one-time, about 2–4 hours spread over the first weeks). See §9. The system must
  make each one a guided step in the dashboard and must keep working (posting privately or skipping a
  platform) while an approval is pending.
- **Platform rules built in from day one:**
  - YouTube: an unverified API project's uploads are locked to private until the project passes the YouTube
    API compliance audit. The OAuth consent screen must be **published to "In production"**, because
    "Testing" refresh tokens expire after 7 days. Re-authorize after publishing. Upload quota is about 6 videos a
    day by default. Set `status.containsSyntheticMedia = true` on every upload (supported since Oct 2024).
  - TikTok: unaudited Content Posting API clients can post only as `SELF_ONLY` (private). Apply for the audit
    early. The adapter must detect the audited state and switch to public. Access tokens last 24 h and refresh
    tokens 365 days, so refresh automatically and alert 30 days before the refresh token expires.
    TikTok Creator Rewards needs videos over 1 minute **and** residence in an eligible country (check the owner's).
  - Meta: Instagram Professional (Creator/Business) account linked to a Facebook Page. Use the Meta app in
    development mode with the owner's account holding a role on the app (own-account use). Use the resumable
    upload path (`rupload`) so no public video URL is needed. Builder: verify both against current Meta docs.
  - TikTok and Meta apps need a privacy-policy / terms URL: a static page on **GitHub Pages** ($0).
- **AI disclosure:** set the synthetic-content flags wherever an API offers them (YouTube
  `containsSyntheticMedia`, TikTok AIGC flag if the API exposes it). Put a short "AI-assisted" line in descriptions.

---

## 3. Approaches considered

### 3.1 System shape. **Chosen: one Python application**
| Option | Trade-off |
|---|---|
| **A. One Python app (chosen)**: scheduler, all stages, FastAPI dashboard, SQLite, in Docker Compose | Fewest moving parts, fully unit-testable, an AI coding session can build and verify all of it. Changing prompts and schedules happens in YAML config or the dashboard, not a visual editor. |
| B. n8n orchestrator + Python render worker (the earlier proposal) | A visual editor for the owner, but n8n workflows are hard to build and test automatically, a separate stats dashboard is still needed, and it adds Postgres and one more service to keep alive. |
| C. Hosted no-code (Make/Zapier) + rendering API | Monthly fees and per-render costs. Breaks the $0 goal. |

### 3.2 Character. **Chosen: original squirrel drawn in code as layered vector art**
| Option | Trade-off |
|---|---|
| **Code-drawn SVG rig (chosen)** | $0, perfectly consistent, every part versioned in git, easy to iterate. Clean flat-cartoon style. Can later be replaced by an artist-made set using the same file layout. |
| AI image → cleaned up | More detail, but splitting it into animatable layers is manual and unpredictable. |
| AI video every time / avatar SaaS | The character drifts between videos, costs money per clip, and looks generic. Rejected. |

### 3.3 Character role. **Chosen: host + visuals**
The squirrel appears full-frame for the hook (0–3 s) and the sign-off. During the explanation it shrinks to a
corner (about 30 % width) and reacts (points, surprised, thinking) while code, diagrams and clips fill the screen.

### 3.4 Rendering stack. **Chosen: Python frame compositor → FFmpeg**
Remotion was found in the plugin catalog. It is rejected for runtime because it needs headless Chrome and Node
on ARM and is heavier to run. Manim is good but slow and over-powered for templates. Chosen: draw each frame with
**skia-python** (fallback: pycairo + cairosvg), pipe raw frames into **FFmpeg**. Builder may swap the drawing
library if it doesn't work on arm64, as long as the template interface stays the same.

### 3.5 Model use (cost-driven, chosen because the owner asked for close-to-zero cost)
- Script writing and rewrite: `claude-sonnet-5-5` ($2 / $10 per M tokens), about $0.02–0.04 per video.
- Topic ranking, metadata, policy filter, frame QA (vision): `claude-haiku-5-5` ($0.10 / $0.50), well under $0.01.
- Fact-check: `claude-sonnet-5-5` with the server-side web search tool, `max_uses` 3.
- All model ids in config. The owner can raise quality to `claude-opus-5-5` at about 2× the script cost.
- Use the official `anthropic` Python SDK, structured outputs (`output_config.format`) for every JSON stage,
  prompt caching on the static persona/system prompt, and the Batches API is **not** used (latency is irrelevant,
  but batching complicates the state machine for small volume. Builder may add it later).

---

## 4. Architecture

```
┌──────────────────────── Oracle ARM VM (Docker Compose) ────────────────────────┐
│ app (Python 3.12)                                                              │
│  scheduler (APScheduler) ──► pipeline state machine (one row per video)        │
│    1 topics     HN API, GitHub trending, arXiv cs.AI/cs.LG RSS, dev RSS,       │
│                 evergreen backlog.yaml → dedupe → rank (Haiku)                 │
│    2 script     Sonnet: persona + topic → Script JSON (beats, visuals, tags)   │
│    3 factcheck  Sonnet + web search → pass / fix / drop                        │
│    4 policy     Haiku: banned-topic + claims filter                            │
│    5 voice      Kokoro TTS (local) → wav + word timestamps → pitch-shift       │
│    6 lipsync    Rhubarb (built from source) → mouth-shape track                │
│                 (fallback: loudness-based mouth open/closed)                   │
│    7 assets     Pexels clips, code images, diagram specs                       │
│    8 render     skia frames → FFmpeg → 1080×1920 30 fps MP4 (+ thumbnail)      │
│    9 qa         ffprobe checks, loudness, duration, Haiku vision on 6 frames   │
│   10 publish    adapters: YouTube · TikTok · Instagram · Facebook              │
│   11 analytics  daily stats pull → DB → topic/format scoring                   │
│  dashboard      FastAPI + Jinja + HTMX + Chart.js (served locally)             │
│  notifier       Telegram bot (alerts + daily summary; optional veto window)    │
│ SQLite (WAL) · /data volume: assets, renders (30-day retention), backups       │
└────────────────────────────────────────────────────────────────────────────────┘
Remote access: Tailscale (free) for the dashboard; Tailscale Funnel exposes only the
OAuth callback over HTTPS when connecting accounts.
```

**Resilience rule:** each stage is idempotent, reads the previous stage's saved output from `/data/jobs/<id>/`,
writes its own, and records the status in SQLite. On failure: retry with backoff (3×), then mark `failed`, alert,
and move on to the next video. A failed stage can be re-run from the dashboard. The scheduler keeps a **buffer of
3 ready-to-post videos** so a bad day never means a missed post.

---

## 5. Components

### 5.1 Channel config (`config/channel.yaml`)
Niche, language, persona, cadence (default 2/day; times per platform), platforms enabled, review mode
(`off` default | `veto` with N-hour window | `approve`), model ids, monthly LLM budget cap, banned topics,
description template, hashtags policy. The dashboard edits it. Secrets live in `.env` only.

### 5.2 Topic engine
- Sources (all free, no auth): Hacker News Firebase API (top/best), GitHub trending page, arXiv RSS (cs.AI, cs.LG,
  cs.SE), a few tech-news RSS feeds (list in config), and `config/backlog.yaml`, a hand-curated plus
  Claude-expanded list of evergreen topics ("How does HTTPS work?", "What is a vector database?").
- Mix: about 60 % evergreen and 40 % trending (config). Evergreen topics age well and keep the channel from
  looking like a news echo.
- Dedupe: normalized title + Haiku similarity check against the last 300 topics.
- Rank (Haiku): curiosity, how well it explains in 60–90 s, visualizability, and later the analytics score of its category.

### 5.3 Script writer
Output (structured JSON, schema-validated):
```
title, hook_line, beats[ {text, expression, pose, visual{template, params}, emphasis_words[]} ],
sign_off, description, hashtags[], category, est_duration_s, sources[]
```
- Persona prompt: the squirrel's name, voice, catchphrase, humour rules (playful, never cringe), reading
  level (smart 15-year-old), 150–210 words (60–90 s), hook in the first 2 s, one idea per video, end on a
  payoff, not "follow for more" spam.
- **Variety guard:** rotate through 6+ formats ("How X works", "X vs Y", "Myth vs fact", "Explain like I'm 5",
  "History of X in 60 s", "One line of code that…"). No two consecutive videos share format plus hook style.
  This is the main defence against "repetitive content".

### 5.4 Fact-check and policy
- Sonnet with web search checks each factual claim, returns `pass | fixed (patched beats) | drop` with sources.
  Max one rewrite cycle, then drop.
- Haiku policy pass: banned topics (health, finance advice, politics, real-person accusations), copyrighted
  characters, and any claim the fact-check marked unsure.

### 5.5 Voice
- **Kokoro-82M** (Apache-2.0), running locally on CPU. Use the Python `kokoro` package or the Kokoro-FastAPI
  arm64 image, whichever works on the VM. English voice chosen at design time, then
  **pitch-shifted +2–4 semitones** with FFmpeg `rubberband` (formant-preserving) to sound like the character.
- Word timestamps from Kokoro if available; otherwise run `faster-whisper` (small, int8, CPU) alignment on the wav.
- Loudness-normalize to −14 LUFS.
- Fallback TTS: Piper. Optional paid upgrade later: ElevenLabs (same interface).

### 5.6 Character rig (the mascot)
- Original design: a cute squirrel with round glasses, big tail, a hoodie in brand colour. Placeholder name
  **"Byte"** (owner may rename in config). Design sheet committed as SVG plus a PNG preview.
- Layered SVG parts in `assets/character/`: body poses (idle, point-left, point-right, thinking, shrug,
  excited, wave), head, eyes (open, half, closed, wide), brows (neutral, raised, frown), **mouth shapes
  A–H + X** (Preston Blair set used by Rhubarb), glasses, tail (separate for sway).
- `expression` and `pose` tags in the script map to part combinations (`rig.yaml`).
- Procedural motion: random blink every 2–5 s, breathing bob (sine), tail sway, eased pose transitions (6 frames),
  squash-bounce on emphasis words, small head tilt on questions.
- Lip-sync: Rhubarb Lip Sync (MIT) built from source in the Docker image (no official arm64 release found).
  If that fails: a loudness envelope → 3 mouth shapes.

### 5.7 Visual templates (9:16, safe zones: avoid the bottom 20 % and right 12 % where platform UI sits)
1. **Hook card**: big squirrel plus 3–6-word punchline text.
2. **Code card**: Pygments-highlighted code, typewriter reveal, line highlight on cue.
3. **Diagram**: small JSON DSL (nodes, edges, groups, labels) → auto layout, animated draw-in, packet/arrow
   motion along edges. Covers most CS explainers (networks, pipelines, data structures).
4. **Comparison split**: X vs Y with checkmarks.
5. **Big number / stat callout.**
6. **Terminal**: commands typing with output.
7. **Stock clip**: Pexels video (free API, licence allows use), cropped to 9:16, darkened under captions.
8. **Title/list card**: 2–4 bullets revealed in turn.
Each template is a pure function `(params, t) → frame layer` with a snapshot test.

### 5.8 Captions, audio, render
- Word-by-word captions synced to the timestamps, current word highlighted, emphasis words coloured.
- Background music from a bundled folder of **CC0 / royalty-free** loops (licence file per track), ducked
  −18 dB under voice. Small pop/whoosh SFX on transitions (CC0).
- Render: 1080×1920, 30 fps, H.264 High, CRF ~20, AAC 192 k, `+faststart`. Target render time under 8 min on
  4 ARM cores for 90 s. Also render a thumbnail/cover frame.
- Duration: 61–90 s by default (passes TikTok's over-1-minute rule; still a Short on YouTube, where the limit is 3 min).

### 5.9 Automated QA gate (replaces human review)
Fail → re-render once → else mark failed and alert:
- ffprobe: resolution, fps, duration window, audio present, size.
- Loudness −14 ±2 LUFS, no silence over 1.2 s.
- Caption coverage ≥ 95 % of spoken words; no text outside the safe zones (checked at layout time).
- Haiku vision on 6 sampled frames: "any broken/overlapping/cut-off text, empty frame, glitch?" → pass/fail.

### 5.10 Publishers (common interface `publish(video, metadata) → PostResult`)
- **YouTube**: Data API v3 resumable upload, `categoryId 28`, `selfDeclaredMadeForKids=false`,
  `containsSyntheticMedia=true`, `#Shorts` in the title or description, privacy from the account state
  (private until the audit passes, then public). Quota tracking.
- **TikTok**: Content Posting API Direct Post, FILE_UPLOAD chunked. Query `creator_info` first (required). Privacy
  `SELF_ONLY` until audited. AIGC flag if available.
- **Instagram**: Graph API Reels container (resumable upload) → poll status → publish. `share_to_feed=true`.
- **Facebook**: Page Reels publishing API (resumable upload).
- Per-platform posting times (config) and staggered by about 30 min. Platform-specific title and hashtags from the script's metadata.
- Each platform failure is isolated: one platform down never blocks the others.

### 5.11 Accounts and tokens
- Dashboard "Accounts" page: Connect button per platform (OAuth), status (connected, expires, audited yes/no,
  quota left), Reconnect button.
- Tokens encrypted at rest (Fernet key in `.env`). Background job refreshes tokens; Telegram alert 7 days before
  any non-refreshable expiry and on any `invalid_grant`.

### 5.12 Analytics and feedback loop
- Daily pull: YouTube Data API stats (views, likes, comments) and YouTube Analytics API (views, average view
  duration, subscribers gained, estimated revenue once monetized); TikTok `video.list` stats; Instagram and
  Facebook insights.
- Scores per category, format and hook style (views at 48 h, normalized per platform) feed topic ranking and format
  rotation weights (bounded, so variety is never lost).
- **Monetization tracker** on the dashboard: YouTube 1,000 subscribers + 10 M Shorts views / 90 days progress
  bar; TikTok 10 k followers progress; alerts the owner when a threshold is reached so they can apply.

### 5.13 Dashboard pages
Overview (totals, 30-day charts per platform, posting streak, LLM spend vs cap, monetization progress) ·
Videos (queue and history, status per stage and per platform, inline player, retry/skip/delete) · Accounts ·
Topics (backlog, add/ban topics) · Settings (channel.yaml editor with validation) · Logs.
Login: single admin password (argon2 hash in `.env`) + reachable only over Tailscale.

### 5.14 Notifications (Telegram)
Daily summary (posted, views, spend); alerts: pipeline stalled > 24 h, buffer empty, token expiring/invalid,
quota hit, upload rejected/removed, budget cap reached, disk > 80 %. Optional veto mode: send preview, publish after N hours unless ❌.

### 5.15 Operations
- Docker Compose services: `app`, optional `kokoro` (if using Kokoro-FastAPI). `restart: unless-stopped`.
- Daily backup of SQLite + config + character assets to Oracle Object Storage (Always Free 20 GB) or a private
  GitHub repo. Renders deleted after 30 days.
- Budget guard: count tokens per call (`response.usage`), stop all LLM stages when the monthly cap is hit, alert.
- To prevent Oracle's idle reclamation, the owner upgrades to Pay-As-You-Go (stays $0 within free limits). A cron
  workload alone isn't guaranteed to count as "active".
- One-command install script: `./install.sh` (Docker, compose up, generates keys, prints the dashboard URL).

---

## 6. Monetization (fewest human steps)
1. **YouTube Partner Program** (primary): automatic once eligible. Owner applies once (AdSense link, tax form).
   Shorts revenue share pays out automatically to AdSense.
2. **Facebook content monetization**: if offered in the owner's country, one-time opt-in.
3. **TikTok Creator Rewards**: only if the owner's country is eligible; videos already over 60 s.
4. Instagram: no general ad share; used for audience growth.
5. Phase 2: auto long-form compilations (higher revenue per view) and optional affiliate slot.

## 7. Costs (about 60 videos/month)
| Item | $/month |
|---|---|
| Oracle VM, Object Storage, Tailscale, GitHub Pages, Telegram, Pexels, all OSS | 0 |
| Claude: scripts (Sonnet) about $0.03 × 60 | about 1.80 |
| Claude: fact-check web search (about 3 searches × $0.01) × 60 | about 1.80 |
| Claude: Haiku tasks (topics, policy, QA vision) | < 0.30 |
| **Total** | **about $2–4** (hard cap $5 by default) |
Optional upgrades: ElevenLabs voice (~$22), Opus scripts (+~$2), artist character (~$50–200 once).

## 8. Milestones (each ends with a runnable, verified result)
- **M0 Setup kit**: repo skeleton, Docker, config schema, install script, GitHub Pages privacy page, setup guide
  for the human checklist (§9). *Owner starts the YouTube and TikTok audits now; they take the longest.*
- **M1 Character**: SVG rig, `rig.yaml`, a test render of the squirrel lip-syncing a sample wav. **Owner checks the look.**
- **M2 Video from a hand-written script**: voice, lip-sync, templates, captions, music, render, QA. **Quality checkpoint.**
- **M3 Content brain**: topics, script, fact-check, policy, budget guard. Daily runs produce finished videos into the buffer.
- **M4 Publishing**: YouTube first, then Meta (IG + FB), then TikTok. Token management, privacy auto-switch.
- **M5 Dashboard + Telegram**: all pages, alerts, daily summary.
- **M6 Analytics loop + monetization tracker**, backups, 7-day unattended soak test on the VM.

## 9. One-time human checklist (the only things the owner must do)
1. Oracle Cloud account → ARM VM (Ubuntu 22.04/24.04) → upgrade to Pay-As-You-Go (stays free) → run `install.sh`.
2. Install Tailscale on the VM and phone/PC.
3. Create a Google account + YouTube channel (brand account) → Google Cloud project → enable YouTube Data API v3
   and YouTube Analytics API → OAuth client → consent screen **published to Production** → connect in the
   dashboard → submit the YouTube API audit form (for public uploads).
4. TikTok account → TikTok for Developers app (Login Kit + Content Posting API, Direct Post) → privacy URL →
   connect → submit the audit.
5. Facebook Page + Instagram Professional account linked to it → Meta developer app (owner as admin) → connect.
6. Anthropic API key with a spend limit; Pexels API key; Telegram bot (BotFather) → paste into `.env` via the installer.
7. Later, when the dashboard says eligible: apply to YouTube Partner Program (+ AdSense), and to TikTok/Facebook
   programs if the country is eligible.

## 10. Risks
| Risk | Mitigation |
|---|---|
| Demonetization for repetitive/AI content | Original mascot, format rotation, fact-checking, low volume, AI labels, no reuse. |
| Audits rejected or slow | Start in M0; private posting keeps the pipeline exercised; YouTube + Meta can be public sooner. |
| Token expiry stops posting silently | Production consent screen, refresh jobs, early alerts, buffer. |
| ARM build issues (Rhubarb, skia, Kokoro) | Documented fallbacks for each; verify in M1/M2 on arm64 (CI with `docker buildx --platform linux/arm64`). |
| Oracle reclaims or loses the VM | Pay-As-You-Go upgrade; daily off-box backups; `install.sh` restore path. |
| Fact errors in published videos | Web-search fact-check, drop on uncertainty, sources stored per video. |
| LLM cost runaway | Hard monthly cap, per-call accounting. |

## 11. Left to the builder
Exact library versions; the diagram auto-layout algorithm; prompt wording (iterate with sample outputs); SQLite
schema details; Kokoro voice pick (try 3, present samples); exact RSS feeds; dashboard styling; whether
Kokoro runs in-process or as a sidecar. Build-time aids available in the plugin catalog (not runtime
dependencies): "Social Media Skills" (hook/short-form script skills, useful when writing prompts) and
"animation-studio" (code-drawn animation reference).

## 12. Verify during build (claims from research that need confirming against current docs)
- Meta: own-account publishing in dev mode without App Review; resumable upload for Reels on IG and FB Pages.
- TikTok: AIGC flag field name on Direct Post; token lifetimes.
- Kokoro word timestamps on arm64 CPU.
- Rhubarb source build on arm64.
- YouTube Shorts eligibility for 61–90 s vertical uploads via API.
