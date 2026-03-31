@echo off
cd /d "%~dp0"
set PYTHONPATH=src
poetry run python -m rat_project.app.main
