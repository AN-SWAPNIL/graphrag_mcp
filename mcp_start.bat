@echo off
cd /d D:\Codes\mcp\graphrag_mcp

echo ========================================
echo   Starting GraphRAG MCP System
echo ========================================
echo.

echo [1/3] Starting Docker containers...
docker-compose up -d

echo.
echo [2/3] Waiting for databases (20 seconds)...
timeout /t 20 /nobreak

echo.
echo [3/3] Starting MCP server...
echo.
echo ========================================
echo   System Ready!
echo   Neo4j:  http://localhost:7474
echo   Qdrant: http://localhost:6333
echo ========================================
echo.

