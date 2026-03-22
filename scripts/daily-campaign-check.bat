@echo off
REM Daily TikTok Campaign Check - Runs at 08:00
REM Checks @newgarmentsclo for new slideshows, launches campaign if 3+ new ones

cd /d "C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)"

"C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\claude.exe" -p "DAILY AUTO-CHECK: Open TikTok profile tiktok.com/@newgarmentsclo in Playwright browser. Scrape the recent posts and count how many NEW slideshows (carousel/image posts) have been posted since the last campaign was launched. Check your memory files for the last campaign date. If there are 3 or more new slideshows, launch a new TikTok campaign following the saved workflow in project_tiktok_campaign_workflow.md with collection URL https://newgarments.store/collections/nicos-pieces-1. Name the campaign 'NEWGARMENTS - Nicos Pieces - [today date]'. Use the new slideshows as Spark Ads creatives. If less than 3 new slideshows, just log that no campaign was needed today." --allowedTools "mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_snapshot,mcp__plugin_playwright_playwright__browser_click,mcp__plugin_playwright_playwright__browser_type,mcp__plugin_playwright_playwright__browser_evaluate,mcp__plugin_playwright_playwright__browser_press_key,mcp__plugin_playwright_playwright__browser_take_screenshot,mcp__plugin_playwright_playwright__browser_fill_form,mcp__plugin_playwright_playwright__browser_wait_for,mcp__plugin_playwright_playwright__browser_tabs,Edit,Read,Write,Glob,Grep,Bash"

echo.
echo === Campaign check completed at %date% %time% ===
echo.
pause
