@echo off
call .\venv\Scripts\activate
python main.py
echo.
echo Script execution finished. Press any key to exit.
pause >nul
deactivate