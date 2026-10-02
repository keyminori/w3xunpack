@echo off
cd /d "%~dp0"
title W3X 一键解包工具

if "%~1"=="" goto usage

echo 开始解包，请稍候...
python "unpack.py" %*
if errorlevel 1 goto fail

echo.
echo 解包完成！输出已放在地图同目录的 _解包输出 文件夹。
goto end

:usage
echo ==========================================
echo   W3X 一键解包工具
echo ==========================================
echo.
echo   把 .w3x 地图文件拖到本脚本图标上松开即可。
echo   可一次拖多个地图。
echo.

:fail
echo.
echo 未完成。请检查：
echo   - 是否正确安装 Python
echo   - 地图是否为本工具支持的 SLK 优化图

:end
echo.
pause