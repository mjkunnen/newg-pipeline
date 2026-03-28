# SOP: Remake Pipeline

Recurring workflow for remaking competitor ads/pins into NEWGARMENTS versions.

## Variants

### Pinterest Pin Remake
1. Check Google Sheet for which pins are already remade (see `reference_pinterest_tracking_sheet.md` in memory)
2. Run `pipeline/remake_pipeline.py` or `pipeline/cloud_pinterest.py`
3. Automated via `.github/workflows/daily-pinterest.yml`

### Competitor Ad Remake (Meta)
1. Download competitor ads via `scout/download_ads.py`
2. Remake via `scout/remake_competitor_ads.py`
3. Output lands in `scout/output/remakes/`

### TikTok Slide Remake
1. Download slides via `scout/download_tiktok_slides.py`
2. Remake via `scout/remake_tiktok_slides.py`
3. Output in `scout/output/tiktok_remakes/`
4. Rules: skip slide 1 (silhouette), maintain flat lay proportions, follow original format

### Decarba Remixer (PPSpy → Meta)
1. Scrapes PPSpy via Oxylabs
2. Claude Vision analyzes competitor ads
3. fal.ai generates NEWGARMENTS versions
4. Meta API launches ads
5. Config: `decarba-remixer/config/products.yaml` + `settings.yaml`

## Critical Rules (all remakes)
- Full outfit required: top + bottom + shoes (never just swap hoodie)
- Reference images required for generation
- No text on outfit images
- Product images: extraction/segmentation only, NO AI generation
- 1:1 fabric accuracy required for product shots
