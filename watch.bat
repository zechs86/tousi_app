@echo off
rem このファイルをダブルクリックすると、イオンの「今日のブリーフィング」を表示します。
rem 別の銘柄を見たいときは、このファイルを右クリック→編集して 8267.T を別コードに変えてください。
chcp 65001 >nul
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" "%~dp0src\watch.py" 8267.T
echo.
pause
