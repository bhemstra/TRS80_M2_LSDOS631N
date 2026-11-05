@echo off
rem ZGET2.BAT - make L631NEW2.DSK from the LS-DOS that zmac-build built
rem
rem Run "python build.py floppy" first (out\floppy). Needs, like GET2_NEW.BAT,
rem trs80gp and the disks of steps 1, 3 and 4 of BUILD.md: l2-631a.dmk,
rem L631BOOT_631A.DSK and L631UTL2.DSK. Then continue with step 7 (TEST2.BAT)
rem and step 8/9 (MAKEBOOT_631N_1S.BAT, MAKEBOOT_631N_2S.BAT).
cd /d %~dp0..
CALL SET_TRS80GP
copy l2-631a.DMK L631NEW2.DSK
set SOUND=
set DISKS=-d0ds -d L631BOOT_631A.DSK -d1ds -d L631UTL2.DSK -d L631NEW2.DSK -d3ds -d dmk-ds#77
set FREHD=-frehd-dir zmac-build\out\floppy
call :del trs80-disk*.dsk

start /wait %TRS80GP% -haste -m2 -50 -vs -win full %SOUND% %DISKS% %FREHD% %GRAF% -itime 0 ^
 -iw "Date" -iy "%%m/%%d/%%y\r%%h:%%i:%%s\r" ^
 -iw "Ready" -i "import2 -n zget2.jcl zget2/jcl:1\r" ^
 -iw "LS-DOS Ready" -i "do zget2\r" ^
 -iw "Job done" -ix

call :del trs80-disk?-?.dsk
echo Job done.
goto :eof

:del
if exist %1 del /q %1
goto :eof
