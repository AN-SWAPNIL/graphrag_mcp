@echo off
cd /d D:\Codes\mcp\graphrag_mcp

echo Stopping Docker containers...
docker-compose down

echo.
echo ========================================
echo   All services stopped
echo ========================================
