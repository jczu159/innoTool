@echo off
echo Building Tiger Missing Commit Finder...
pyinstaller commit_audit.spec --noconfirm
echo.
echo Done! EXE is at dist\TigerMissingCommitFinder.exe
pause
