@echo off
rem BlenderForge launcher:  forge input.md output.blend [options]
rem Finds Blender via %BLENDER%, PATH, or the newest install under Program Files.
setlocal enabledelayedexpansion
set "BL=%BLENDER%"
if not defined BL for %%I in (blender.exe) do set "BL=%%~$PATH:I"
if not defined BL (
  for /f "delims=" %%D in ('dir /b /ad /o-n "%ProgramFiles%\Blender Foundation\Blender*" 2^>nul') do (
    if not defined BL if exist "%ProgramFiles%\Blender Foundation\%%D\blender.exe" set "BL=%ProgramFiles%\Blender Foundation\%%D\blender.exe"
  )
)
if not defined BL (
  echo Blender not found. Install it or set BLENDER to the full path of blender.exe.
  exit /b 2
)
"%BL%" --background --python "%~dp0build.py" -- %*
exit /b %ERRORLEVEL%
