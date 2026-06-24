@echo off
rem このファイルをダブルクリックすると分析プログラムが動きます。
rem chcp 65001 = コンソールをUTF-8にする(絵文字や記号を正しく表示するため)
chcp 65001 >nul
set PYTHONUTF8=1
"%~dp0.venv\Scripts\python.exe" "%~dp0src\main.py"
echo.
pause
