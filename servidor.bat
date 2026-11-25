@echo off
rem Atalho para os comandos do servidor:  servidor.bat versoes | promover 0.7.0 | link | status ...
cd /d "%~dp0"
uv run --extra servidor python -m servidor %*
