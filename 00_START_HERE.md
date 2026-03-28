# NEWGARMENTS — Competitor Creative Research & Pipeline

## What This Folder Is

The operational hub for NEWGARMENTS' automated creative pipeline. Contains:
- **Competitor research** — scraping, analysis, and reports on streetwear competitors (TikTok, Meta, Pinterest, PipiAds)
- **Ad creative pipeline** — generating, remaking, and launching ads across Meta/TikTok/Pinterest
- **Product pipeline** — Taobao → Shopify product listing via scraping + SegFormer + Zapier
- **Decarba Remixer** — TypeScript pipeline: PPSpy scrape → Claude Vision → fal.ai remake → Meta launch
- **Ad Command Center** — Railway-deployed dashboard for campaign management
- **Scheduled automation** — GitHub Actions workflows + local .bat/.ps1 schedulers

## Key Subsystems (by folder)

| Folder | Purpose | Language |
|---|---|---|
| `scout/` | Competitor scraping, ad downloading, TikTok/Pinterest remake | Python |
| `pipeline/` | Pinterest remake pipeline, image generation, cloud delivery | Python |
| `decarba-remixer/` | PPSpy → Vision → fal.ai → Meta launch pipeline | TypeScript |
| `ad-command-center/` | Railway dashboard app for campaign ops | Python |
| `launch/` | Meta campaign launcher | Python |
| `config/` | Brand voice, audience, generation configs | YAML/JSON |
| `scripts/` | Windows schedulers (.bat/.ps1) | Batch/PS |
| `.github/workflows/` | CI/CD: daily scrape, pinterest remake, product sync, campaign launch | YAML |
| `shopify-app/` | Shopify Liquid snippets (collection sorting) | Liquid |

## Fresh Session Checklist

1. Read this file
2. Read `01_CURRENT_STATE.md` for current file map and known issues
3. Read `CLAUDE.md` for security rules and credential handling
4. Check `.github/workflows/` for what's automated
5. If working on remakes: read memory files `feedback_remake_workflow.md` and `feedback_product_images.md`
6. If working on Shopify: access is via Zapier MCP ONLY (never direct API)

## Ambiguity Warnings

- Many research `.md` files at root level are historical/one-off — they are NOT current truth
- Multiple versions of slideshow data files exist (`slideshow_data_v3.js`, `v4`, `v5`) — check which is active
- Multiple PipiAds research scripts (`v2`, `v3`, `v4`) — latest version is authoritative
- `snapshot_*.md` files are temporary browser snapshots from TikTok campaign creation — not persistent docs
- Debug screenshots (`debug_*.png`) are one-off artifacts

## Pointer

See `01_CURRENT_STATE.md` for the current file map, working state, and known risks.
