@echo off
schtasks /create /tn "NEWGARMENTS Daily Campaign Check" /tr "C:\Users\maxku\OneDrive\Bureaublad\competitor creative research (NEWG)\scripts\daily-campaign-check.bat" /sc daily /st 08:00 /f
echo.
echo Task scheduled! Will run daily at 08:00.
pause
