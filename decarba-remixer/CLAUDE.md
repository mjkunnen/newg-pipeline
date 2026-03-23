# Decarba Ad Remixer

Automated system that scrapes competitor (Decarba) ads from PPSpy, analyzes them, and remakes them for NEWGARMENTS brand.

## Architecture
```
Oxylabs API (PPSpy HTML) → Cheerio parse → Filter top ads → Download creatives
    ├── Static ads → Claude Vision analysis → fal.ai NanoBanana 2 remake
    └── Video ads → FFmpeg trim last frame(s) → append NEWGARMENTS end card
            ↓
    Google Drive upload → Meta Marketing API campaign launch (PAUSED, needs approval)
```

## Tech Stack
- TypeScript (Node.js, ES2022, NodeNext modules)
- Oxylabs Web Scraper API (replaces Playwright — no browser management, proxy built-in)
- Cheerio for HTML parsing
- fal.ai NanoBanana 2 (`@fal-ai/client`) for image generation
- OpenAI GPT-4o Vision for ad analysis
- FFmpeg for video trim + endcard concat
- Sharp for text overlays on images
- Meta Marketing API for campaign creation

## Key Files
- `src/scraper/ppspy.ts` — Oxylabs + Cheerio scraper, downloads to output/raw/{date}/
- `src/scraper/types.ts` — All TypeScript interfaces
- `src/analyzer/vision.ts` — Claude Vision ad analysis
- `src/analyzer/matcher.ts` — Match ad style to NEWGARMENTS products
- `src/remixer/image.ts` — fal.ai NanoBanana 2 static ad remake (2 variations)
- `src/remixer/video.ts` — FFmpeg video trim + endcard
- `src/launcher/meta.ts` — Meta Marketing API (prepare drafts + launch with AUTO_LAUNCH=true)
- `src/output/drive.ts` — Google Drive upload (placeholder, TODO)
- `src/index.ts` — Main orchestrator
- `config/settings.yaml` — max_ads, trim_seconds, collections, auto flags
- `config/products.yaml` — NEWGARMENTS product catalog per collection

## Commands
- `npm run build` — compile TS
- `npm run start` — full pipeline (scrape → analyze → remix → drafts)
- `npm run scrape` — only scrape PPSpy
- `npm run start -- --skip-scrape` — remix using last scrape
- `npm run start -- --skip-launch` — skip Meta campaign creation

## Auth / Credentials (.env)
- OXYLABS_USERNAME / OXYLABS_PASSWORD — Oxylabs Web Scraper API
- PPSPY_COOKIES — session cookies for PPSpy (logged-in state)
- FAL_KEY — fal.ai API key
- OPENAI_API_KEY — OpenAI GPT-4o Vision
- META_ACCESS_TOKEN / META_AD_ACCOUNT_ID / META_PAGE_ID — Meta Marketing API
- AUTO_LAUNCH — must be "true" to actually create Meta campaigns (safety)

## Important
- Campaign drafts saved to output/campaigns/{date}/drafts.json for review before launch
- Raw HTML saved to output/raw/{date}/raw.html for debugging scraper selectors
- PPSpy DOM selectors may need tuning — check raw.html if parsing returns 0 ads
- Video remix requires ffmpeg installed locally
- Boss communicates in Dutch, prefers terse direct output
