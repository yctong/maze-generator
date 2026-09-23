@echo off
setlocal enabledelayedexpansion
title Maze Generator ^& Coloring Sheet Engine
color 0F

:: Always operate from the folder this script lives in, no matter how it was launched.
cd /d "%~dp0"

set "SCRIPT=generate_maze_script.py"

:: Session settings (persist while the menu is open)
set "OUTDIR=."
set "MAX_SEARCH="
set "JOBS="
set "STYLE=deceptive"
set "LAYOUT=corners"
set "LOOPS=0"
set "PAGE=sheet"
set "TITLE="
set "PDF=N"

:: ------------------------------------------------------------------
:: Environment checks
:: ------------------------------------------------------------------
if not exist "%SCRIPT%" (
    echo [ERROR] %SCRIPT% was not found next to this launcher.
    echo         Expected location: %~dp0%SCRIPT%
    echo.
    pause
    exit /b 1
)

:: Pick an interpreter. A Python that already has Pillow always wins, so a
:: bare "py -3" pointing at a fresh install does not shadow a working one.
set "PY="
set "PY_ANY="
for %%p in ("python" "py -3" "python3") do (
    if not defined PY (
        %%~p --version >nul 2>&1
        if not errorlevel 1 (
            if not defined PY_ANY set "PY_ANY=%%~p"
            %%~p -c "import PIL" >nul 2>&1
            if not errorlevel 1 set "PY=%%~p"
        )
    )
)
if not defined PY set "PY=%PY_ANY%"
if not defined PY (
    echo [ERROR] No working Python interpreter was found on your PATH.
    echo         Install Python 3 from https://www.python.org/downloads/
    echo         and make sure "Add Python to PATH" is ticked.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%v in ('%PY% --version 2^>^&1') do set "PYVER=%%v"

:: Pillow is required for rendering.
%PY% -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Required package "Pillow" is missing.
    set /p installpil="    Install it now with pip? (Y/N, default Y): "
    if "!installpil!"=="" set "installpil=Y"
    if /i "!installpil!"=="Y" (
        echo.
        %PY% -m pip install --upgrade pillow
        %PY% -c "import PIL" >nul 2>&1
        if errorlevel 1 (
            echo.
            echo [ERROR] Pillow could not be installed. Please install it manually:
            echo         %PY% -m pip install pillow
            echo.
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] Cannot continue without Pillow.
        pause
        exit /b 1
    )
)

:: ------------------------------------------------------------------
:: Main menu
:: ------------------------------------------------------------------
:MENU
cls
echo ====================================================================
echo             MAZE GENERATOR ^& COLORING SHEET ENGINE
echo ====================================================================
echo   Interpreter : %PY%  (%PYVER%)
echo   Output dir  : %OUTDIR%
if defined MAX_SEARCH (echo   Seed search : %MAX_SEARCH% seeds) else (echo   Seed search : auto)
if defined JOBS (echo   Workers     : %JOBS%) else (echo   Workers     : auto ^(CPU-1^))
echo   Style       : %STYLE%, %LAYOUT% layout, %LOOPS% loop(s), %PAGE% page
echo ====================================================================
echo.
echo   [1] Standard Deceptive Maze     (12 rows x 10 cols, Auto-Optimized)
echo   [2] Junior / Easy Maze          (8 rows x 8 cols, Auto-Optimized)
echo   [3] Advanced / Complex Maze     (16 rows x 12 cols, Auto-Optimized)
echo   [4] Master / Extra Large Maze   (20 rows x 15 cols, Auto-Optimized)
echo   [5] Reproduce Specific Seed     (Custom Seed ^& Dimensions)
echo   [6] Custom Dimensions           (Enter your own rows ^& cols)
echo   [7] Batch Generate              (Many mazes + optional PDF book)
echo   [8] View Latest Generated Maze  (Open PNGs)
echo   [9] Settings                    (Style, layout, page, title, PDF, workers)
echo   [0] Exit
echo.
echo ====================================================================
set "choice="
set /p choice="Enter your choice (0-9): "

if "%choice%"=="1" ( set "G_ROWS=12" & set "G_COLS=10" & set "G_LABEL=Standard Deceptive Maze" & goto RUN_GEN )
if "%choice%"=="2" ( set "G_ROWS=8"  & set "G_COLS=8"  & set "G_LABEL=Junior / Easy Maze" & goto RUN_GEN )
if "%choice%"=="3" ( set "G_ROWS=16" & set "G_COLS=12" & set "G_LABEL=Advanced Complex Maze" & goto RUN_GEN )
if "%choice%"=="4" ( set "G_ROWS=20" & set "G_COLS=15" & set "G_LABEL=Master Extra Large Maze" & goto RUN_GEN )
if "%choice%"=="5" goto CUSTOM_SEED
if "%choice%"=="6" goto CUSTOM_DIMS
if "%choice%"=="7" goto BATCH
if "%choice%"=="8" goto OPEN_IMAGES
if "%choice%"=="9" goto SETTINGS
if "%choice%"=="0" exit /b 0

echo [WARN] Invalid selection. Please choose a number between 0 and 9.
timeout /t 2 >nul
goto MENU

:: ------------------------------------------------------------------
:: Presets and custom runs
:: ------------------------------------------------------------------
:CUSTOM_SEED
cls
echo ====================================================================
echo Reproduce Specific Seed
echo ====================================================================
call :ASK_INT s_rows "Enter rows" 12 4 60
if errorlevel 1 goto MENU
call :ASK_INT s_cols "Enter cols" 10 4 60
if errorlevel 1 goto MENU
call :ASK_INT s_seed "Enter seed number" "" 0 999999999
if errorlevel 1 goto MENU

set "G_ROWS=!s_rows!"
set "G_COLS=!s_cols!"
set "G_SEED=!s_seed!"
set "G_LABEL=Seed !s_seed! Reproduction"
goto RUN_GEN

:CUSTOM_DIMS
cls
echo ====================================================================
echo Custom Dimensions Configuration
echo ====================================================================
call :ASK_INT c_rows "Enter rows (4-60)" 12 4 60
if errorlevel 1 goto MENU
call :ASK_INT c_cols "Enter cols (4-60)" 10 4 60
if errorlevel 1 goto MENU

set "G_ROWS=!c_rows!"
set "G_COLS=!c_cols!"
set "G_LABEL=Custom !c_rows! x !c_cols! Maze"
goto RUN_GEN

:RUN_GEN
cls
echo ====================================================================
echo %G_LABEL% (%G_ROWS% x %G_COLS%)
echo ====================================================================
echo Each maze is saved as its own numbered file pair (maze_001.png,
echo maze_002.png, ...), so nothing you generated earlier is overwritten.
echo.
if defined G_SEED (
    set "G_COUNT=1"
) else (
    call :ASK_INT G_COUNT "How many mazes" 1 1 200
    if errorlevel 1 goto MENU
)
echo.
echo Generating !G_COUNT! maze(s)...
echo.
call :BUILD_ARGS
if not exist "%OUTDIR%" mkdir "%OUTDIR%" 2>nul
%PY% "%SCRIPT%" --rows %G_ROWS% --cols %G_COLS% --outdir "%OUTDIR%" --count !G_COUNT! !EXTRA_ARGS!
set "RC=!errorlevel!"
set "G_SEED="
if not "!RC!"=="0" goto GEN_FAILED
goto POST_GEN

:: ------------------------------------------------------------------
:: Batch generation
:: ------------------------------------------------------------------
:BATCH
cls
echo ====================================================================
echo Batch Generate
echo ====================================================================
echo All mazes go into one timestamped folder as numbered file pairs
echo (maze_001.png, maze_002.png, ...) so nothing gets overwritten.
echo Every sheet is independently auto-optimized, so the batch comes out
echo varied. Each sheet prints its seed if you want to reproduce a
echo particular one later.
echo.
call :ASK_INT b_count "How many mazes" 5 1 200
if errorlevel 1 goto MENU
call :ASK_INT b_rows "Enter rows (4-60)" 12 4 60
if errorlevel 1 goto MENU
call :ASK_INT b_cols "Enter cols (4-60)" 10 4 60
if errorlevel 1 goto MENU

set "STAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "STAMP=!STAMP: =0!"
set "BATCHDIR=%OUTDIR%\batch_!STAMP!"
mkdir "!BATCHDIR!" 2>nul

set "G_SEED="
set "G_COUNT=!b_count!"
call :BUILD_ARGS
%PY% "%SCRIPT%" --rows !b_rows! --cols !b_cols! --outdir "!BATCHDIR!" --count !b_count! !EXTRA_ARGS!
set "RC=!errorlevel!"

echo.
echo ====================================================================
if "!RC!"=="0" (
    echo Batch complete. !b_count! mazes written.
) else (
    echo [ERROR] Batch failed (exit code !RC!). Scroll up for details.
)
echo Folder: !BATCHDIR!
echo ====================================================================
set "openb="
set /p openb="Open the batch folder now? (Y/N, default Y): "
if "!openb!"=="" set "openb=Y"
if /i "!openb!"=="Y" start "" explorer "!BATCHDIR!"
echo.
pause
goto MENU

:: ------------------------------------------------------------------
:: Settings
:: ------------------------------------------------------------------
:SETTINGS
cls
echo ====================================================================
echo Settings
echo ====================================================================
echo   [1] Output directory   (current: %OUTDIR%)
if defined MAX_SEARCH (echo   [2] Seed search depth  ^(current: %MAX_SEARCH%^)) else (echo   [2] Seed search depth  ^(current: auto^))
if defined JOBS (echo   [3] Parallel workers   ^(current: %JOBS%^)) else (echo   [3] Parallel workers   ^(current: auto^))
echo   [4] Maze style         (current: %STYLE%)
echo   [5] START/FINISH spots (current: %LAYOUT%)
echo   [6] Extra loops        (current: %LOOPS%, 0 = single solution)
echo   [7] Page size          (current: %PAGE%)
if defined TITLE (echo   [8] Sheet title        ^(current: !TITLE!^)) else (echo   [8] Sheet title        ^(current: none^))
echo   [9] PDF book for batches (current: %PDF%)
echo   [R] Reset to defaults
echo   [0] Back to main menu
echo.
set "sc="
set /p sc="Choose (0-9, R): "

if "%sc%"=="1" (
    set "newdir="
    set /p newdir="New output directory (blank = current folder): "
    if "!newdir!"=="" (set "OUTDIR=.") else (set "OUTDIR=!newdir!")
    if not exist "!OUTDIR!" (
        mkdir "!OUTDIR!" 2>nul
        if errorlevel 1 (
            echo [WARN] Could not create "!OUTDIR!" - keeping the current folder.
            set "OUTDIR=."
            timeout /t 2 >nul
        )
    )
    goto SETTINGS
)
if "%sc%"=="2" (
    call :ASK_INT ms "Seeds to evaluate (blank = auto)" "" 1 100000
    if errorlevel 1 (set "MAX_SEARCH=") else (set "MAX_SEARCH=!ms!")
    goto SETTINGS
)
if "%sc%"=="3" (
    call :ASK_INT jb "Worker processes (blank = auto)" "" 1 64
    if errorlevel 1 (set "JOBS=") else (set "JOBS=!jb!")
    goto SETTINGS
)
if "%sc%"=="4" goto PICK_STYLE
if "%sc%"=="5" goto PICK_LAYOUT
if "%sc%"=="6" (
    call :ASK_INT lp "Loops to add (0 = single solution)" 0 0 200
    if not errorlevel 1 set "LOOPS=!lp!"
    goto SETTINGS
)
if "%sc%"=="7" goto PICK_PAGE
if "%sc%"=="8" (
    set "TITLE="
    set /p TITLE="Title (use {n} for the sheet number, blank = none): "
    goto SETTINGS
)
if "%sc%"=="9" (
    if "!PDF!"=="Y" (set "PDF=N") else (set "PDF=Y")
    goto SETTINGS
)
if /i "%sc%"=="R" (
    set "OUTDIR=."
    set "MAX_SEARCH="
    set "JOBS="
    set "STYLE=deceptive"
    set "LAYOUT=corners"
    set "LOOPS=0"
    set "PAGE=sheet"
    set "TITLE="
    set "PDF=N"
    goto SETTINGS
)
if "%sc%"=="0" goto MENU
goto SETTINGS

:PICK_STYLE
echo.
echo Maze style:
echo   [1] deceptive    Deep decoys, anti-greedy forks, exit lures (default)
echo   [2] backtracker  Long twisting corridors, few dead ends
echo   [3] prim         Many short branches, busy look
echo   [4] kruskal      Even mix of short and medium dead ends
echo   [5] wilson       Unbiased uniform maze
echo   [6] hunt-kill    Long winding passages, straighter runs
set "pk="
set /p pk="Choose (1-6, blank = keep current): "
if "!pk!"=="1" set "STYLE=deceptive"
if "!pk!"=="2" set "STYLE=backtracker"
if "!pk!"=="3" set "STYLE=prim"
if "!pk!"=="4" set "STYLE=kruskal"
if "!pk!"=="5" set "STYLE=wilson"
if "!pk!"=="6" set "STYLE=hunt-kill"
goto SETTINGS

:PICK_LAYOUT
echo.
echo START / FINISH placement:
echo   [1] corners      Top-left to bottom-right (default)
echo   [2] sides        Left wall to right wall, random rows
echo   [3] top-bottom   Top wall to bottom wall, random columns
echo   [4] random       Random opposite walls every sheet
set "pk="
set /p pk="Choose (1-4, blank = keep current): "
if "!pk!"=="1" set "LAYOUT=corners"
if "!pk!"=="2" set "LAYOUT=sides"
if "!pk!"=="3" set "LAYOUT=top-bottom"
if "!pk!"=="4" set "LAYOUT=random"
goto SETTINGS

:PICK_PAGE
echo.
echo Page size:
echo   [1] sheet        1800 x 2400 px, 3:4 (default)
echo   [2] letter       US Letter 8.5 x 11 in
echo   [3] a4           A4 210 x 297 mm
echo   [4] square       8 x 8 in
set "pk="
set /p pk="Choose (1-4, blank = keep current): "
if "!pk!"=="1" set "PAGE=sheet"
if "!pk!"=="2" set "PAGE=letter"
if "!pk!"=="3" set "PAGE=a4"
if "!pk!"=="4" set "PAGE=square"
goto SETTINGS

:: ------------------------------------------------------------------
:: Viewing results
:: ------------------------------------------------------------------
:OPEN_IMAGES
cls
call :OPEN_LATEST
if "!FOUND!"=="0" (
    echo [WARN] No generated maze images found in "%OUTDIR%".
    echo     Generate a maze first with options 1-7.
) else (
    echo Opened the most recent maze images from "%OUTDIR%".
)
echo.
pause
goto MENU

:GEN_FAILED
echo.
echo ====================================================================
echo [ERROR] Generation failed (exit code !RC!).
echo Scroll up for the Python traceback.
echo ====================================================================
echo.
pause
goto MENU

:POST_GEN
echo.
echo ====================================================================
echo Generation Complete:
echo !G_COUNT! maze(s) saved in "%OUTDIR%" as numbered file pairs:
echo   - maze_NNN.png          (Printable Clean Sheet)
echo   - maze_NNN_solution.png (Solution Key)
echo Scroll up for each sheet's file name and seed.
echo ====================================================================
echo.
if !G_COUNT! GTR 1 (
    set "view_now="
    set /p view_now="Open the output folder now? (Y/N, default Y): "
    if "!view_now!"=="" set "view_now=Y"
    if /i "!view_now!"=="Y" start "" explorer "%OUTDIR%"
) else (
    set "view_now="
    set /p view_now="Would you like to open the generated maze images now? (Y/N, default Y): "
    if "!view_now!"=="" set "view_now=Y"
    if /i "!view_now!"=="Y" call :OPEN_LATEST
)

echo.
pause
goto MENU

:: ------------------------------------------------------------------
:: Helpers
:: ------------------------------------------------------------------

:: OPEN_LATEST - opens the newest maze sheet in OUTDIR plus its solution key.
:: Sets FOUND=1 when something was opened.
:OPEN_LATEST
set "FOUND=0"
set "LATEST="
for /f "delims=" %%f in ('dir /b /a-d /o-d "%OUTDIR%\*.png" 2^>nul ^| findstr /v /i /e "_solution.png"') do (
    if not defined LATEST set "LATEST=%%~nf"
)
if defined LATEST (
    start "" "%OUTDIR%\!LATEST!.png"
    if exist "%OUTDIR%\!LATEST!_solution.png" start "" "%OUTDIR%\!LATEST!_solution.png"
    set "FOUND=1"
)
exit /b 0

:: BUILD_ARGS - assembles optional CLI flags into EXTRA_ARGS
:BUILD_ARGS
set "EXTRA_ARGS="
if defined G_SEED set "EXTRA_ARGS=!EXTRA_ARGS! --seed !G_SEED!"
if defined MAX_SEARCH set "EXTRA_ARGS=!EXTRA_ARGS! --max-search !MAX_SEARCH!"
if defined JOBS set "EXTRA_ARGS=!EXTRA_ARGS! --jobs !JOBS!"
set "EXTRA_ARGS=!EXTRA_ARGS! --style !STYLE! --layout !LAYOUT! --page !PAGE!"
if not "!LOOPS!"=="0" set "EXTRA_ARGS=!EXTRA_ARGS! --loops !LOOPS!"
if defined TITLE set "EXTRA_ARGS=!EXTRA_ARGS! --title "!TITLE!""
:: A book only makes sense when more than one sheet is written.
if not defined G_COUNT set "G_COUNT=1"
if /i "!PDF!"=="Y" if !G_COUNT! GTR 1 set "EXTRA_ARGS=!EXTRA_ARGS! --pdf"
exit /b 0

:: ASK_INT <varname> <prompt> <default|""> <min> <max>
:: Repeats until a valid integer in range is entered.
:: Returns errorlevel 1 when the answer is blank and there is no default.
:ASK_INT
set "_var=%~1"
set "_prompt=%~2"
set "_default=%~3"
set "_min=%~4"
set "_max=%~5"
:ASK_INT_LOOP
set "_ans="
if "%_default%"=="" (
    set /p _ans="%_prompt%: "
) else (
    set /p _ans="%_prompt% [default %_default%]: "
)
if "!_ans!"=="" (
    if "%_default%"=="" exit /b 1
    set "_ans=%_default%"
)
:: Reject anything that is not purely digits.
for /f "delims=0123456789" %%x in ("!_ans!") do (
    echo [WARN] "!_ans!" is not a whole number. Try again.
    goto ASK_INT_LOOP
)
if !_ans! LSS %_min% (
    echo [WARN] Value must be at least %_min%. Try again.
    goto ASK_INT_LOOP
)
if !_ans! GTR %_max% (
    echo [WARN] Value must be at most %_max%. Try again.
    goto ASK_INT_LOOP
)
set "%_var%=!_ans!"
exit /b 0
