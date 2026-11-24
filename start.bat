@echo off
rem Start het interactieve startscherm van cfd-rans-postproc.
rem Werkt vanaf elke locatie: de werkmap wordt op de repo-root gezet.
cd /d "%~dp0"
py -m src.cfd_postproc.gui
if errorlevel 1 pause
