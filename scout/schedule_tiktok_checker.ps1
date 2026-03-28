# Register daily TikTok Carousel Checker task at 10:00 AM
# Runs Claude Code which executes the pipeline + uploads via Zapier MCP
# Run this script once as Administrator to set up the scheduled task.

$batPath = "C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scripts\daily-tiktok-checker.bat"

$action = New-ScheduledTaskAction -Execute $batPath

$trigger = New-ScheduledTaskTrigger -Daily -At 10:00AM

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "NEWGARMENTS_TikTok_Checker" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Daily TikTok carousel checker — Claude Code runs pipeline, remakes with NEWGARMENTS outfits, uploads to Drive via Zapier" `
    -Force

Write-Host "Task registered: NEWGARMENTS_TikTok_Checker (daily at 10:00 AM)"
Write-Host "Runs: scripts\daily-tiktok-checker.bat"
