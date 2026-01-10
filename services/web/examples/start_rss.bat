@echo off
cd /d "C:\Users\AhFei\Documents\code\source2RSS"

:: 启动 Edge（如果尚未运行）
tasklist | findstr /C:"msedge.exe" >nul
if %errorlevel% neq 0 (
    start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=1536

:: 可选：等待几秒让 Edge 启动
timeout /t 3 /nobreak >nul
)

:: 启动你的 Python 程序（用死循环包裹，退出就重启）
:loop
.env\Scripts\python.exe -m src.node.as_r_agent
echo Program exited at %date% %time%. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop