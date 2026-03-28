@echo off
REM Daily TikTok Carousel Checker & Remake - Runs at 10:00
REM Claude Code runs the pipeline, then uploads remakes to Drive + logs to Sheets via Zapier MCP

cd /d "C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)"

REM Pull latest code
git pull origin master

REM Ensure dirs exist
if not exist "logs" mkdir logs
if not exist "scout\output" mkdir scout\output

"C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\claude.exe" -p "DAILY TIKTOK CHECKER: Run the TikTok carousel checker pipeline. Step by step: 1) Run: python scout/tiktok_checker.py — this scrapes 13 competitor TikTok accounts via Apify, selects the top 3 carousels by views from the last 7 days, downloads slides, and remakes each slide with NEWGARMENTS outfits using fal.ai. It outputs a manifest JSON. 2) Read the manifest file at scout/output/tiktok_manifest.json to get the list of remade images. 3) For EACH entry in the manifest: first upload the local image file to tmpfiles.org using curl: curl -s -F file=@FILEPATH https://tmpfiles.org/api/v1/upload — parse the returned JSON for the URL, then convert it to a direct download link by inserting /dl/ after tmpfiles.org/ (e.g. tmpfiles.org/12345/file.png becomes tmpfiles.org/dl/12345/file.png). 4) Use the direct download URL with Zapier google_drive_upload_file to upload to Google Drive folder ID 13NrwgIuoZevzMfoS2DExXUqa7em6zclr (TikTok Carousels folder). Name the file with the entry filename. 5) For EACH entry, add a row to Google Sheets spreadsheet ID 1BQ54wjilxW3F8rQFnVjwCRJtBTPDrSj3U5D0XYHjsgY, worksheet 'TikTok Carousels', with columns: username, post_id, post_url, view_count, num_slides, slide_num, outfit, filename, status=done, date_processed. 6) Report summary: how many carousels processed, how many slides remade, any errors. If the script returns no manifest or zero entries, report that no new carousels were found today." --allowedTools "mcp__claude_ai_Zapier__google_drive_upload_file,mcp__claude_ai_Zapier__google_drive_create_folder,mcp__claude_ai_Zapier__google_drive_find_a_folder,mcp__claude_ai_Zapier__google_sheets_create_spreadsheet_row,mcp__claude_ai_Zapier__google_sheets_lookup_spreadsheet_row,mcp__claude_ai_Zapier__google_sheets_get_many_spreadsheet_rows_advanced,Edit,Read,Write,Glob,Grep,Bash"

echo.
echo === TikTok checker completed at %date% %time% === >> logs\tiktok-checker.log
