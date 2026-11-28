@echo off
rem MDM RT kit: logs, crash traces and system info into results\ (close MDM RT first).
setlocal
set "R=%~dp0results"
if not exist "%R%" mkdir "%R%"
if exist "%APPDATA%\mdm-rt\logs" xcopy /e /i /y /q "%APPDATA%\mdm-rt\logs" "%R%\logs" >nul
if exist "%APPDATA%\mdm-rt\crashes" xcopy /e /i /y /q "%APPDATA%\mdm-rt\crashes" "%R%\crashes" >nul
rem a panic's message and backtrace (MDM writes it before it ends), and the download list (addresses, errors)
if exist "%APPDATA%\mdm-rt\crash.log" copy /y "%APPDATA%\mdm-rt\crash.log" "%R%\" >nul
if exist "%APPDATA%\mdm-rt\downloads.json" copy /y "%APPDATA%\mdm-rt\downloads.json" "%R%\" >nul
rem Windows' own record of MDM RT's crashes: faulting module, exception code, address
wevtutil qe Application /q:"*[EventData[Data='misterdownloadmanager.exe']]" /c:30 /rd:true /f:text > "%R%\crash-events.txt" 2>&1
for /d %%d in ("%ProgramData%\Microsoft\Windows\WER\ReportArchive\AppCrash_misterdownload*" "%ProgramData%\Microsoft\Windows\WER\ReportQueue\AppCrash_misterdownload*" "%LOCALAPPDATA%\Microsoft\Windows\WER\ReportArchive\AppCrash_misterdownload*" "%LOCALAPPDATA%\Microsoft\Windows\WER\ReportQueue\AppCrash_misterdownload*") do xcopy /e /i /y /q "%%d" "%R%\wer\%%~nxd" >nul 2>&1
ver > "%R%\windows-version.txt"
systeminfo > "%R%\systeminfo.txt" 2>&1
reg query "HKCU\Software\Chromium\NativeMessagingHosts\com.misterdownloadmanager.host" > "%R%\nmhost-registry.txt" 2>&1
dir /s "%~dp0MDM RT" > "%R%\files.txt" 2>&1
echo Writing dxdiag (takes a minute)...
dxdiag /t "%R%\dxdiag.txt"
echo Done: %R%
pause
