@echo off
rem Runs the portal locally at http://localhost:8000
rem
rem   start.bat          start the server (builds the frontend the first time)
rem   start.bat build    rebuild the frontend first, after changing frontend code
rem
rem Settings are in backend\.env (see .env.example). Stop the server with Ctrl+C.

setlocal
cd /d "%~dp0"
set PORT=8000
rem Links in emails point here. Overrides PUBLIC_BASE_URL in backend\.env.
set PUBLIC_BASE_URL=http://localhost:%PORT%

if not exist backend\.env (
    echo backend\.env is missing. Copy .env.example to backend\.env and fill it in.
    exit /b 1
)

if /i "%~1"=="build" goto build
if not exist frontend\out\index.html goto build
goto backend

:build
echo === Building the frontend ===
pushd frontend
if not exist node_modules (
    call npm ci || goto failed
)
call npm run build || goto failed
popd

:backend
echo === Updating the database ===
pushd backend
python -m alembic upgrade head || goto failed
rem The standards checklist, plus demo systems (added only to an empty database),
rem all owned by the seed admin from backend\.env.
python -m app.seed --demo || goto failed

echo === Portal running at %PUBLIC_BASE_URL%  (Ctrl+C to stop) ===
rem Opens the browser a few seconds later, once the server is up.
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" %PUBLIC_BASE_URL%"
python -m uvicorn app.main:app --port %PORT%
popd
exit /b 0

:failed
echo.
echo Something went wrong above. The portal did not start.
popd
exit /b 1
