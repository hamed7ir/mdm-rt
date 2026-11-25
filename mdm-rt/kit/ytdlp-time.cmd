@echo off
rem MDM RT kit: how long yt-dlp takes on this tablet, step by step, into results\ytdlp-time\.
rem   ytdlp-time.cmd                          asks for the YouTube address (paste it) and a proxy (Enter: none)
rem   ytdlp-time.cmd "<address>" [proxy]      the address IN QUOTES (cmd cuts an unquoted one at its "=");
rem                                           proxy as in MDM's Options, e.g. http://127.0.0.1:10809
rem 1. yt-dlp --version: Python and yt-dlp starting
rem 2. MDM's own look-up (-J) with QuickJS for YouTube's JavaScript challenge, a fresh cache (the first look-up)
rem 3. the same again (yt-dlp's cache filled: later look-ups)
rem 4. YouTube's android_vr client (needs no JavaScript), for comparison
setlocal EnableDelayedExpansion
set "K=%~dp0"
set "H=%K%MDM RT\helpers"
set "U=%~1"
set "P=%~2"
rem an unquoted address arrives cut at its "=": its second half then stands where the proxy goes
if defined P if "!P:://=!"=="!P!" (
  echo The address was cut at its "=". Put it in quotes, or run ytdlp-time.cmd alone and paste it when asked.
  pause
  exit /b 1
)
if not defined U (
  echo Paste the YouTube video address ^(right-click, or the window menu: Edit, Paste^), then Enter:
  set /p "U="
  echo Proxy as in MDM's Options ^(for example http://127.0.0.1:10809^), or just Enter for none:
  set /p "P="
)
if not defined U set "U=https://www.youtube.com/watch?v=0mCmaUPwqdM"
set "PX="
if defined P set "PX=--proxy "!P!""
set "R=%K%results\ytdlp-time"
if not exist "%R%" mkdir "%R%"
set "C=%R%\cache"
set "T=%R%\times.txt"
echo yt-dlp timing on %COMPUTERNAME% for !U! > "%T%"
if defined P echo proxy !P! >> "%T%"

echo 1. version...
echo 1 version start !time! >> "%T%"
"%H%\yt-dlp.exe" --version > "%R%\1-version.txt" 2>&1
echo 1 version end   !time! >> "%T%"

echo 2. first look-up (QuickJS, fresh cache) - this can take minutes...
echo 2 lookup start !time! >> "%T%"
"%H%\yt-dlp.exe" -v -J --no-playlist --no-warnings !PX! --cache-dir "%C%" --js-runtimes "quickjs:%H%\qjs.exe" "!U!" > "%R%\2-lookup.json" 2> "%R%\2-lookup-log.txt"
echo 2 lookup end   !time! exit !errorlevel! >> "%T%"

echo 3. second look-up (cache filled)...
echo 3 lookup start !time! >> "%T%"
"%H%\yt-dlp.exe" -v -J --no-playlist --no-warnings !PX! --cache-dir "%C%" --js-runtimes "quickjs:%H%\qjs.exe" "!U!" > "%R%\3-lookup.json" 2> "%R%\3-lookup-log.txt"
echo 3 lookup end   !time! exit !errorlevel! >> "%T%"

echo 4. look-up with the android_vr client (no JavaScript)...
echo 4 lookup start !time! >> "%T%"
"%H%\yt-dlp.exe" -v -J --no-playlist --no-warnings !PX! --cache-dir "%C%" --extractor-args "youtube:player_client=android_vr" "!U!" > "%R%\4-lookup.json" 2> "%R%\4-lookup-log.txt"
echo 4 lookup end   !time! exit !errorlevel! >> "%T%"

type "%T%"
echo.
echo Done. Zip results\ytdlp-time with 7-Zip RT and send it.
pause
