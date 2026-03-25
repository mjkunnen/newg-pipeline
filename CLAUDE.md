# NEWGARMENTS Pipeline

## SECURITY RULES — NOOIT OVERTREDEN

1. NOOIT API keys, tokens, passwords, of secrets hardcoden in broncode
2. ALTIJD environment variables gebruiken: `process.env.*` (TypeScript/JS) of `os.getenv()` (Python)
3. NOOIT credentials loggen, printen, of in console output tonen
4. NOOIT `.env` files committen naar git — check dat `.gitignore` `.env` bevat
5. ALTIJD `.env.example` bijhouden met placeholder waarden (geen echte keys)
6. GitHub Actions secrets via `${{ secrets.* }}` — nooit inline
7. Bij ELKE commit: scan of er geen hardcoded credentials in zitten voordat je pusht
8. Als je een nieuwe API key nodig hebt, vraag de gebruiker om deze in `.env` te zetten — genereer NOOIT een bestand met echte credentials

## Security Details

- NEVER put real values as fallback defaults in `os.getenv("KEY", "real-value-here")` — use `None` or raise an error
- NEVER put credentials in .yaml, .json, .toml config files
- ALL secrets go in `.env` (which is gitignored) — NOWHERE else
- When creating new scripts, ALWAYS use `dotenv` + `os.getenv()` from the start
- If you see a hardcoded credential anywhere, REMOVE IT IMMEDIATELY and replace with env var
- The pre-commit hook will block commits with secrets — do NOT bypass it with --no-verify
- `.env.example` contains the list of required env vars (no real values)

## Credentials Reference (env var names only)
- `FAL_KEY` — fal.ai API
- `APIFY_TOKEN` — Apify scraping
- `OPENAI_API_KEY` — OpenAI
- `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID` / `META_PIXEL_ID` — Meta Ads
- `OXYLABS_USERNAME` / `OXYLABS_PASSWORD` — Oxylabs proxy
- `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET` / `SHOPIFY_SHOP` — Shopify
- `HF_TOKEN` — HuggingFace
- `GOOGLE_SHEET_ID` / `PRODUCT_SHEET_ID` — Google Sheets
- `ZAPIER_WEBHOOK_URL` — Zapier

## Shopify
- Access is via Zapier MCP tools ONLY. Never use direct Shopify API or ask for access token.

## Communication
- Boss communicates in Dutch, prefers terse direct output
- No trailing summaries unless asked
