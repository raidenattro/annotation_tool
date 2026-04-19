@echo off
setlocal

cd /d "%~dp0"
set "LOG_FILE=%~dp0run_tool.log"

where python >nul 2>&1
if errorlevel 1 (
	echo [ERROR] Python not found in PATH.
	echo Please install Python or activate your conda environment first.
	pause
	exit /b 1
)

python -c "import flask, cv2" >nul 2>&1
if errorlevel 1 (
	echo [ERROR] Missing dependencies. Please run:
	echo   pip install -r requirements.txt
	pause
	exit /b 1
)

echo [%date% %time%] launching tool... > "%LOG_FILE%"
start "AnnotationTool" /min cmd /c "cd /d \"%~dp0\" && python tool_launcher.py >> \"%LOG_FILE%\" 2>&1"

echo Tool is starting.
echo If browser does not open, visit: http://127.0.0.1:5000
echo Log file: %LOG_FILE%
exit /b 0
