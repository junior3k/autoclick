@echo off
rem Sobe o servidor de atualizacoes e o reinicia sozinho se cair. Log: servidor\dados\servidor.log
cd /d "%~dp0"
if not exist "servidor\dados" mkdir "servidor\dados"
:laco
echo [%date% %time%] iniciando >> "servidor\dados\servidor.log"
uv run --extra servidor python -m servidor rodar >> "servidor\dados\servidor.log" 2>&1
echo [%date% %time%] servidor parou (codigo %errorlevel%); reiniciando em 5 s >> "servidor\dados\servidor.log"
timeout /t 5 /nobreak >nul
goto laco
