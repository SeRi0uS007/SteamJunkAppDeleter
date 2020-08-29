@echo off

echo Initiating Virtual Environment
python -m venv venv

echo Updating pip
venv\Scripts\python -m pip install --upgrade pip

echo Updating SetupTools
venv\Scripts\python -m pip install --upgrade setuptools

echo Installing depending modules
venv\Scripts\python -m pip install -r requirements.txt

pause