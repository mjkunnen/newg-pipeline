$action = New-ScheduledTaskAction -Execute 'C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scripts\daily-campaign-check.bat'
$trigger = New-ScheduledTaskTrigger -Daily -At '08:00AM'
Register-ScheduledTask -TaskName 'NEWGARMENTS_Daily_Campaign' -Action $action -Trigger $trigger -Description 'Daily check for new TikTok slideshows and campaign launch' -Force
Write-Host "Task scheduled! Will run daily at 08:00."
