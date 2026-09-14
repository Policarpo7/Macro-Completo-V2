@echo off
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo Instale Python 3.11 ou superior com o Python Launcher.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto erro
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
echo Instalacao concluida. Abra iniciar.bat.
pause
exit /b 0
:erro
echo A instalacao falhou. Consulte a mensagem acima.
pause
exit /b 1
