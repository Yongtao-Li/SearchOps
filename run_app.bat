@echo off
setlocal

REM --- CHANGE THIS to your conda install folder ---
set "CONDA_ROOT=C:\Users\%USERNAME%\mambaforge"

REM --- CHANGE THIS to your env name ---
set "ENV_NAME=searchops"

REM --- CHANGE THIS to your app entry file ---
set "APP_FILE=app.py"

call "%CONDA_ROOT%\Scripts\activate.bat" "%CONDA_ROOT%"
call conda activate %ENV_NAME%

REM Use python -m so we don't depend on streamlit.exe being on PATH
python -m streamlit run "%APP_FILE%"

endlocal