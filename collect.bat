@echo off
rem このファイルをダブルクリックすると、その日のデータを収集してDBに貯めます。
rem 毎日(または数日おきに)実行すると、あなただけの株価データが蓄積されていきます。
chcp 65001 >nul
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" "%~dp0src\collect.py"
echo.
pause
