@echo off
REM One-time setup for Windows. Double-click or run from the VS Code terminal.
where py >nul 2>nul && (set PY=py) || (set PY=python)
if not exist venv (
  echo Creating virtual environment...
  %PY% -m venv venv || goto :fail
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :fail
python manage.py migrate || goto :fail
python manage.py seed_demo
echo.
echo Setup finished. Start the app with run.bat  (or press F5 in VS Code)
pause
exit /b 0
:fail
echo.
echo Something failed. Read the message above, then see README.md > Troubleshooting.
pause
exit /b 1
