@echo off
rem MDM RT kit: where a YouTube look-up's time goes on this tablet (ytdlp-speed.py), into results\ytdlp-speed\.
rem   ytdlp-speed.cmd                          asks for the YouTube address (paste it) and a proxy (Enter: none)
rem   ytdlp-speed.cmd "<address>" [proxy]      the address IN QUOTES (cmd cuts an unquoted one at its "=")
rem Five ways of looking the video up, each twice: about 10 to 20 minutes on a Surface RT.
setlocal EnableDelayedExpansion
set "K=%~dp0"
set "H=%K%MDM RT\helpers"
set "U=%~1"
set "P=%~2"
if defined P if "!P:://=!"=="!P!" (
  echo The address was cut at its "=". Put it in quotes, or run ytdlp-speed.cmd alone and paste it when asked.
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
set "R=%K%results\ytdlp-speed"
echo This takes 10 to 20 minutes. Leave the tablet on.
"%H%\python.exe" -I "%K%ytdlp-speed.py" "%H%" "!U!" "%R%" "!P!"
echo.
echo Done. Zip results\ytdlp-speed with 7-Zip RT and send it.
pause
