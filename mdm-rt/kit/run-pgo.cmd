@echo off
rem MDM RT PGO kit: starts the COUNTING build of MDM RT. Every counted program (MDM RT, and the ffmpeg/ffprobe and
rem QuickJS that yt-dlp starts for it) writes its counts into profiles\ when it exits normally:
rem count-<process id>.profraw.
setlocal
set "K=%~dp0"
if not exist "%K%profiles" mkdir "%K%profiles"

rem a normal MDM RT still running would take over, and nothing would be counted
tasklist /nh /fi "imagename eq misterdownloadmanager.exe" 2>nul | "%SystemRoot%\System32\find.exe" /i "misterdownloadmanager.exe" >nul
if not errorlevel 1 (
  echo MDM RT is running. Close it first: File ^> Exit ^(also check the notification area^), then run this again.
  pause
  exit /b 1
)

rem self-test: a tiny counting program must write its counts here (else the whole run would count nothing)
set "LLVM_PROFILE_FILE=%K%profiles\selftest.profraw"
"%K%tools\pgo-selftest.exe" 100000 >nul
if not exist "%K%profiles\selftest.profraw" (
  echo The PGO self-test wrote no counts. Please send me a screenshot of this window.
  pause
  exit /b 1
)
del "%K%profiles\selftest.profraw"
rem and the counting helpers yt-dlp starts: QuickJS (YouTube's challenge) and ffmpeg
set "LLVM_PROFILE_FILE=%K%profiles\selftest-qjs.profraw"
"%K%MDM RT\helpers\qjs.exe" --help >nul
set "LLVM_PROFILE_FILE=%K%profiles\selftest-ffmpeg.profraw"
"%K%MDM RT\helpers\ffmpeg.exe" -version >nul 2>&1
for %%f in (qjs ffmpeg) do if not exist "%K%profiles\selftest-%%f.profraw" (
  echo The counting %%f.exe wrote no counts. Please send me a screenshot of this window.
  pause
  exit /b 1
)
del "%K%profiles\selftest-qjs.profraw" "%K%profiles\selftest-ffmpeg.profraw"
echo PGO self-test ok. Starting the counting MDM RT...

rem yt-dlp's cache in the kit, fresh: YouTube's challenge then runs in the counting QuickJS at least once (yt-dlp
rem keeps its answer per YouTube player version)
set "XDG_CACHE_HOME=%K%profiles\cache"
set "LLVM_PROFILE_FILE=%K%profiles\count-%%p.profraw"
start "" "%K%MDM RT\misterdownloadmanager.exe"
