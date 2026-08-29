@echo off
REM ============================================
REM  交响乐之雨 演奏复刻 - Windows 打包脚本
REM  用法: 双击运行, 产物在 dist\SymphonicRain.exe
REM  需要: Python 3.10+ / pip install pygame pyinstaller
REM ============================================
D:\Python311\Scripts\pyinstaller.exe -w --name SymphonicRain --add-data "src:src" --add-data "runtime;runtime" main.py
