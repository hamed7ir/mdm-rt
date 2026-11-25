@echo off
rem MDM RT preview kit: start MDM RT with ANGLE on Direct3D 9 (Tegra's path; MDM_ANGLE is read by MDM RT's EGL setup).
set MDM_ANGLE=d3d9
start "" "%~dp0MDM RT\misterdownloadmanager.exe"
