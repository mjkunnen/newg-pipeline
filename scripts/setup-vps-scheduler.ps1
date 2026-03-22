# Register NEWGARMENTS daily tasks on VPS
# Run as Administrator: powershell -ExecutionPolicy Bypass -File scripts\setup-vps-scheduler.ps1

$repoRoot = Split-Path -Parent $PSScriptRoot

# Task 1: Daily Pinterest remake at 08:00
$remakeAction = New-ScheduledTaskAction -Execute "$repoRoot\scripts\daily-remake-check.bat"
$remakeTrigger = New-ScheduledTaskTrigger -Daily -At '08:00AM'
Register-ScheduledTask -TaskName 'NEWGARMENTS_Daily_Remake' -Action $remakeAction -Trigger $remakeTrigger -Description 'Daily Pinterest board auto-remake pipeline' -Force

# Task 2: Daily TikTok campaign check at 09:00
$campaignAction = New-ScheduledTaskAction -Execute "$repoRoot\scripts\daily-campaign-check.bat"
$campaignTrigger = New-ScheduledTaskTrigger -Daily -At '09:00AM'
Register-ScheduledTask -TaskName 'NEWGARMENTS_Daily_Campaign' -Action $campaignAction -Trigger $campaignTrigger -Description 'Daily TikTok campaign check' -Force

Write-Host ""
Write-Host "Both tasks scheduled:"
Write-Host "  - NEWGARMENTS_Daily_Remake    at 08:00 (Pinterest remakes)"
Write-Host "  - NEWGARMENTS_Daily_Campaign  at 09:00 (TikTok campaigns)"
Write-Host ""
Write-Host "Verify with: Get-ScheduledTask | Where-Object {`$_.TaskName -like 'NEWGARMENTS*'}"
