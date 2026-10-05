@echo off
REM ============================================================================
REM  漁벤져스 탁도 프로브 v3.1 — 빌드·업로드 (한글 계정명 회피)
REM
REM  ld.exe / esptool 이 C:\Users\<한글>\AppData\... 경로를 못 읽으므로
REM  빌드 폴더를 ASCII 경로(C:\ac\build)로 강제한다.
REM
REM  사용법:  build_upload.bat  [스케치폴더]  [COM포트]
REM  예:      build_upload.bat  C:\ardsketch\bringup_check  COM3
REM ============================================================================

setlocal

set SKETCH=%~1
set PORT=%~2
if "%SKETCH%"=="" set SKETCH=C:\ardsketch\bringup_check
if "%PORT%"==""   set PORT=COM3

set FQBN=esp32:esp32:esp32doit-devkit-v1
set BUILD=C:\ac\build

echo === compile : %SKETCH%
arduino-cli compile --fqbn %FQBN% --build-path %BUILD% "%SKETCH%"
if errorlevel 1 goto :fail

echo === upload  : %PORT%
arduino-cli upload -p %PORT% --fqbn %FQBN% --input-dir %BUILD% "%SKETCH%"
if errorlevel 1 goto :fail

echo === done. 시리얼 모니터 115200 baud
echo     arduino-cli monitor -p %PORT% -c baudrate=115200
goto :eof

:fail
echo.
echo *** 실패. 위 로그를 확인하세요.
echo     - "cannot open output file" 이면 BUILD 경로에 한글이 섞인 것
echo     - "Failed to connect" 이면 BOOT 버튼을 누른 채 업로드 시작
exit /b 1
