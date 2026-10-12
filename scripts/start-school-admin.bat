@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0ensp-vrp-ime-helper-school.exe' -Verb RunAs"
