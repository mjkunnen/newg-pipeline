@echo off
REM Daily Pinterest Board Remake Check - Runs at 08:00
REM Claude Code checks for new pins, remakes them, uploads to Drive, logs in Sheet

cd /d "%~dp0.."

REM Pull latest code first
git pull origin master

claude -p "DAILY AUTO-REMAKE: Run the /check-board workflow. Step by step: 1) Read the tracking Google Sheet (ID: 1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY, worksheet Blad1) using Zapier google_sheets to get ALL existing pin_id values from column G. 2) Fetch pins from Pinterest board ID 1003176954437607618 using Zapier Pinterest MCP. 3) Compare: only process pins whose pin_id is NOT already in the sheet. 4) For each new pin, remake it using fal.ai EDIT endpoint (https://queue.fal.run/fal-ai/nano-banana-2/edit) with full outfit (top+bottom+shoes). Use Shopify CDN URLs from board_remakes_proper/remake_batch.py for product refs. Cycle through the 6 outfit combos. Use status_url and response_url from queue response for polling - NEVER construct URLs manually. 5) Upload remakes to Google Drive folder (ID: 1crvIaZtrMmuXslneAkX_q4rgcb1J5-FU) in a subfolder for today's date. 6) Add a row to the tracking sheet for each completed remake with pin_id in column G, pin_url in F, outfit_combo in E, status=done in D, date in C. 7) Report summary of what was done. CRITICAL: Always use /edit endpoint, always full outfit (top+bottom+shoes), always mention white t-shirt underneath in prompt, never use fal_client.subscribe()." --allowedTools "mcp__claude_ai_Zapier__pinterest_create_pin,mcp__claude_ai_Zapier__pinterest_api_request_beta,mcp__claude_ai_Zapier__google_sheets_get_many_spreadsheet_rows_advanced,mcp__claude_ai_Zapier__google_sheets_lookup_spreadsheet_rows_advanced,mcp__claude_ai_Zapier__google_sheets_lookup_spreadsheet_row,mcp__claude_ai_Zapier__google_sheets_create_spreadsheet_row,mcp__claude_ai_Zapier__google_sheets_get_spreadsheet_by_id,mcp__claude_ai_Zapier__google_drive_find_a_file,mcp__claude_ai_Zapier__google_drive_find_a_folder,mcp__claude_ai_Zapier__google_drive_create_folder,mcp__claude_ai_Zapier__google_drive_upload_file,mcp__claude_ai_Zapier__google_drive_retrieve_files_from_google_drive,Edit,Read,Write,Glob,Grep,Bash"

echo.
echo === Remake check completed at %date% %time% ===
