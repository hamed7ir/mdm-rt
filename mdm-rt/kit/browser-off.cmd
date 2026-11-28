@echo off
rem MDM RT preview kit: remove what browser-on.cmd registered.
"%~dp0MDM RT\misterdownloadmanager-nmhost.exe" --unregister
if errorlevel 1 (echo Removing failed: error %errorlevel%) else (echo Done.)
pause
