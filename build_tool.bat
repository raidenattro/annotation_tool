@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Installing runtime dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install runtime dependencies.
  exit /b 1
)

echo [2/3] Installing packaging dependency...
python -m pip install pyinstaller
if errorlevel 1 (
  echo Failed to install pyinstaller.
  exit /b 1
)

echo [3/3] Building AnnotationTool package...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name AnnotationTool --add-data "annotation_tool.html;." --collect-all cv2 --collect-all numpy --collect-all flask --collect-all jinja2 --collect-all werkzeug --collect-all click --collect-all itsdangerous --exclude-module numpy.f2py.tests --exclude-module pytest tool_launcher.py
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo.
echo Build success.
echo Run this file for delivery use:
echo   dist\AnnotationTool\AnnotationTool.exe
pause
