# SOP: Daily Automation

## GitHub Actions (runs automatically)

| Workflow | File | What it does |
|---|---|---|
| Daily Scrape | `.github/workflows/daily-scrape.yml` | Scrapes competitor ads, has backup cron + skip-if-ran guard |
| Daily Pinterest | `.github/workflows/daily-pinterest.yml` | Remakes Pinterest pins, has backup cron + skip-if-ran guard |
| Daily Products | `.github/workflows/daily-products.yml` | Product sync pipeline |
| Launch Campaigns | `.github/workflows/launch-campaigns.yml` | Meta campaign launch (manual trigger) |

## Local Schedulers (Windows)

| Script | Purpose |
|---|---|
| `scripts/daily-remake-check.bat` | Check/trigger remake pipeline |
| `scripts/daily-campaign-check.bat` | Check campaign status |
| `scripts/daily-tiktok-checker.bat` | Run TikTok checker |
| `scripts/daily-remake.bat` | Run remake pipeline |
| `scripts/setup-scheduler.bat` / `.ps1` | Set up Windows Task Scheduler |
| `scout/schedule_tiktok_checker.ps1` | Schedule TikTok checker via PS |

## Monitoring
- Ad Command Center dashboard: `ad-command-center/` (deployed on Railway)
- Local dashboard: `dashboard.html` / `build_dashboard.py`

## Troubleshooting
- Check `.github/workflows/` for cron schedules and skip guards
- All secrets via GitHub Actions `${{ secrets.* }}` — never inline
- If a workflow fails, check if env vars are set in repo secrets
