@echo off
rem MDM RT preview kit: register this copy's native messaging host for Venetium, Chrome, Edge, Brave and Firefox
rem (HKCU: per user; a manifest file is written beside the host program).
"%~dp0MDM RT\misterdownloadmanager-nmhost.exe" --register
if errorlevel 1 (echo Registering failed: error %errorlevel%) else (echo Done. Restart Venetium completely.)
pause
