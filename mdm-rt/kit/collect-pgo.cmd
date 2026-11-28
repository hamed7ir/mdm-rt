@echo off
rem MDM RT PGO kit: after File > Exit: lists the counts in profiles\ and copies MDM RT's logs beside them.
setlocal
set "K=%~dp0"
if not exist "%K%profiles" (
  echo No profiles folder: start MDM RT with run-pgo.cmd first.
  pause
  exit /b 1
)
rem MDM RT writes its counts only when it really exits (the X only hides it in the notification area)
tasklist /nh /fi "imagename eq misterdownloadmanager.exe" 2>nul | "%SystemRoot%\System32\find.exe" /i "misterdownloadmanager.exe" >nul
if not errorlevel 1 (
  echo MDM RT is still running, so its counts are not written yet. The X only hides it in the notification area.
  echo Exit it: File ^> Exit, or right-click its icon in the notification area ^> Exit. Then run this again.
  pause
  exit /b 1
)
if exist "%APPDATA%\mdm-rt\logs" xcopy /e /i /y /q "%APPDATA%\mdm-rt\logs" "%K%profiles\logs" >nul
ver > "%K%profiles\windows-version.txt"
echo Counts written (the biggest file is MDM RT's own, the smaller ones ffmpeg's, ffprobe's and QuickJS's):
dir /o-s "%K%profiles\*.profraw"
echo.
echo Zip the profiles folder with 7-Zip RT and send it back.
pause
