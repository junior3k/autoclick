@echo off
rem Testa, empacota, assina e publica a versao atual (entra no canal beta).
rem Exemplos:  publicar.bat            publicar.bat --exe            publicar.bat --subir menor --notas "texto"
cd /d "%~dp0"
uv run --extra servidor python -m servidor publicar %*
echo.
echo Para liberar a todos: servidor.bat promover NUMERO-DA-VERSAO   ^|   o link publico e https://ac.cabro.me/download
pause
