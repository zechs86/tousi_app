@echo off
rem このファイルをダブルクリックすると、ブラウザでダッシュボードが開きます。
rem スマホから見るには、同じWiFiで http://(PCのIPアドレス):8501 を開いてください。
chcp 65001 >nul
set PYTHONUTF8=1
"%~dp0.venv\Scripts\streamlit.exe" run "%~dp0src\dashboard.py"
pause
