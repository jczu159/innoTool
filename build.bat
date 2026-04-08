@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building EXE...
pyinstaller ^
  --onefile ^
  --windowed ^
  --name "TigerReleaseBranchHelper" ^
  --add-data "*.py;." ^
  main.py

echo.
echo Done! EXE is in dist\TigerReleaseBranchHelper.exe
pause
