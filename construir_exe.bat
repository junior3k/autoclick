@echo off
setlocal
cd /d "%~dp0"
rem Gera dist\Autoclick\Autoclick.exe (sem precisar de Python no computador de quem for usar).
rem Para incluir o OCR opcional no pacote, rode antes: uv sync --extra ocr
uv sync
if errorlevel 1 goto erro
uv run --with pyinstaller pyinstaller autoclick.spec --noconfirm --clean
if errorlevel 1 goto erro
if exist botoes.exemplo.json copy /y botoes.exemplo.json dist\Autoclick\ >nul
echo.
echo Pronto: dist\Autoclick\Autoclick.exe  (copie a pasta dist\Autoclick inteira)
pause
exit /b 0
:erro
echo.
echo Falhou. Veja a mensagem acima.
pause
exit /b 1
