@echo off
setlocal
cd /d "%~dp0"
if not exist "node_modules\node\bin\node.exe" (
  echo Frontend dependencies are missing. Run npm install first.
  exit /b 1
)
"node_modules\node\bin\node.exe" "node_modules\vite\bin\vite.js" --host 127.0.0.1 %*
