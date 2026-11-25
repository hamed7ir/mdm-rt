@echo off
rem MDM RT preview kit: start MDM RT with ANGLE on Direct3D 11 (feature level 9_3 and up: Adreno; Tegra's 9_1 is too low).
set MDM_ANGLE=d3d11
start "" "%~dp0MDM RT\misterdownloadmanager.exe"
