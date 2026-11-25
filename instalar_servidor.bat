@echo off
rem Primeira instalacao do servidor. Uso:  instalar_servidor.bat updates.seudominio.com
cd /d "%~dp0"
if "%~1"=="" (
  echo Uso: instalar_servidor.bat SEU.DOMINIO   ^(ex.: updates.exemplo.com^)
  pause & exit /b 1
)
uv run --extra servidor python -m servidor instalar --dominio %1 --tarefa
echo.
echo Guarde o TOKEN e a copia da chave privada mostrados acima. Depois leia servidor\LEIAME.md.
pause
