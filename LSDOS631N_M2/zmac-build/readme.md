Building LS-DOS with zmac
=========================

This directory contains the files needed to build LS-DOS 6.3.1 level N
for the Model II from the sources in `../lsdos631` with
[zmac](https://github.com/gp48k/zmac) (George Phillips) on the host,
instead of MRAS inside trs80gp. It makes:

- **a hard disk that boots by itself**: `out/hd/lsdos631n-hd.hdv`, for a
  Model II (or 12, 16, 6000) with a hard disk boot ROM, trs80gp or FreHD.
  Drive `:0` is the hard disk, the floppy drives are `:1` and `:2`.
- **the normal floppy system**: its files in `out/floppy`, which
  `ZGET2.BAT` puts on a boot floppy in trs80gp, like `GET2_NEW.BAT` does
  with the MRAS build.

| File          | Contents                                                     |
|---------------|--------------------------------------------------------------|
| `build.py`    | assembles everything, makes the hard disk image              |
| `mklib.py`    | builds SYS6/SYS7/SYS8 from the library commands, as BLDLIBS/CMD does |
| `mklsdos.py`  | writes the hard disk image: boot area, GAT, HIT, directory, files |
| `ZGET2.BAT`, `zget2.jcl` | put the floppy build on `L631NEW2.DSK` in trs80gp |
| `test/`       | `test.mjs` boots the hard disk image in a Model II emulator under Node |

Building
--------

Needs Python 3 and zmac. `build.py` takes zmac from `--zmac`, `$ZMAC` or
the PATH, or else clones and builds it in `work/zmac` (git, make and a C
compiler; on Windows it uses the `zmac.exe` from that clone).

    python3 build.py            # both
    python3 build.py hd         # only the hard disk image
    python3 build.py floppy     # only the floppy system

The sources are copied to `work/hd` or `work/floppy` with Unix line ends,
and for the hard disk `BUILDVER/ASM` there gets `@HD` set to -1. The
sources themselves stay as MRAS wants them; see "zmac and MRAS" below.
Then lowcore (BOOT/SYS), SYSRES (SYS0), SYS1-SYS13, the library
commands, SYS6-8 (from `../lsdos631/other/l631lib?.dat`) and the
utilities, in the order of `BUILD631/JCL`. MRAS makes the `.EQU` files
the modules include with XREF; `build.py` makes them from zmac's symbol
tables.

The floppy build gives the files the MRAS build makes (`lowcore.cim`,
`sys0.cmd` ... `sys13.cmd`, `sys6.cmd`-`sys8.cmd` as the libraries, the
utilities); with `@HD` off they are byte for byte what zmac makes of the
unchanged GmEsoft sources.

Testing the hard disk image:

    node test/test.mjs

It boots the image, answers the date and time, checks the drives (DEVICE,
FREE), writes files with DUMP and COPY, boots again and reads them back.

Floppy disks
------------

The Model II boot track (what the boot ROM loads, with `BOOT` at 1000H
and `DIAG` at 1400H) is not in these sources: a boot floppy starts as a
copy of the LS-DOS 6.3.1A disk in trs80gp (`l2-631a.dmk`, step 1 of
`../BUILD.md`), as in the MRAS flow. With the disks of steps 1, 3 and 4
(`l2-631a.dmk`, `L631BOOT_631A.DSK`, `L631UTL2.DSK`):

    python build.py floppy
    zmac-build\ZGET2.BAT

`ZGET2.BAT` starts trs80gp with `out/floppy` as the FreHD directory,
formats a scratch disk on `:3`, imports the files there and copies them
onto `L631NEW2.DSK` as GETNEW/JCL and GETUTILS/JCL do. Then go on with
step 7 (`TEST2.BAT`) and steps 8 and 9 (`MAKEBOOT_631N_1S.BAT`,
`MAKEBOOT_631N_2S.BAT`) for the final `.dmk` and `.hfe` images.

The hard disk
-------------

The switches in `../lsdos631/buildver.asm`:

    @HD     EQU  0   ; -1 to boot from the hard disk
    HDDIR   EQU  1   ; hard disk directory cylinder

With `@HD` on:

- `lowcore.asm`: DCT 0 is the hard disk (`hddvr2.asm`, put after the
  floppy driver in the space for drivers below 1200H), physical floppy
  drives 0 and 1 are `:1` and `:2`.
- `sysinit4.asm`: SYSINIT leaves DCT 0 alone instead of setting it up
  from what the floppy boot sector left.
- `hdboot2.asm` is the loader the boot ROM starts.

The drive has 101 cylinders, 8 heads and 32 sectors of 512 bytes per
track (13 MB, the trs80gp layout). Each 256 byte LS-DOS sector is the
first half of a physical sector; that keeps the driver small and without
a buffer, and LS-DOS sees 6464K. LS-DOS sees 202 cylinders of 4 heads
(physical cylinder n is LS-DOS cylinders 2n and 2n+1), 128 sectors and 8
granules of 4K per cylinder.

| LS-DOS cylinder | Contents                                          |
|-----------------|---------------------------------------------------|
| 0               | boot area (BOOT/SYS)                              |
| 1               | directory: GAT, HIT, 32 directory sectors (256 files) |
| 2-201           | files                                             |

The boot area, as 512 byte sectors of cylinder 0 head 0 (from 0):

| Sector | Contents                                                      |
|--------|---------------------------------------------------------------|
| 0-7    | filler (sector 1 byte 2 is the directory cylinder)           |
| 8      | `hdboot2.asm`, starting with `/* END BOOT */`                 |
| 9-26   | memory 0000H-23FFH: lowcore with SYS0 loaded on top           |
| 27-30  | video memory F800H-FFFFH (the logo SYS0 brings)               |

The boot ROM reads sectors from cylinder 0 head 0 into memory from 0000H
until one starts with `/* END BOOT */` and jumps past it. The loader moves
to 7E00H, turns the ROM off, works out whether the drive numbers its
sectors from 0 (trs80gp) or 1, loads the memory image, tells the driver
the numbering and starts SYSINIT at 1E00H.

The driver does read (9), verify (10), write (13) and write system sector
(14); reads of the directory cylinder return error 6, as LS-DOS expects.
FORMAT does not format the hard disk; `mklsdos.py` writes it formatted.

On the disk: SYS0-SYS13, BACKUP, FORMAT, DISKCOPY, PATCH, REPAIR, LOG,
COMM, DATECONV, HELP, MEMDISK/DCT, COM/DVR, the CLICK, FORMS and KSM
filters, and NOTICE/TXT with the copyright and permission notice that has
to go along with copies of LS-DOS.

zmac and MRAS
-------------

The sources are not changed for zmac (only for the hard disk, by `@HD`).
`build.py` runs zmac with `--mras` and, in its copies only:

- puts `ZMPRE/ASM` (`PRELUDE` in `build.py`) in front of each module:
  macros for what zmac lacks. `COM` (a comment record in the /CMD file)
  does nothing there; afterwards `build.py` puts the records in front of
  the /CMD file as MRAS writes them: the module name (the output file's,
  6 characters), then a comment record for each `COM` that was assembled
  (it finds them in zmac's listing). `LORG` (load the code elsewhere than it runs, in FORMAT
  and BACKUP) is done with zmac's PHASE/DEPHASE, and `ORG` is a macro too
  because MRAS keeps the load offset over a later ORG, which zmac does not
  allow inside PHASE (`.ORG` stays the built-in one).
- changes a few spellings zmac does not take, with the same code
  (`EDITS` in `build.py`): the unused `NUL` symbol (an operator in zmac),
  the `LIST` label in `lblist.asm`, `DC 11,-18` as `DC 11,0EEH`,
  `(IX+0FFH)` as `(IX-1)` in MEMDISK, a doubly defined `CLDATA$` in COM,
  and a `:` for a `;` in `sys3.asm`.

Status
------

The hard disk image works in the emulator of `test/` (and the browser
version it comes from); it has not run in trs80gp or on real hardware
yet. `ZGET2.BAT` has not been run.

MRAS 1.1a and XREF (from `../lsdos631/tools`), run under LS-DOS in that
emulator on these sources, assemble LOWCORE, SYSRES, SYS1-SYS5,
SYS9-SYS13, FORMAT and BACKUP without errors, with `@HD` off and on. The
files load the same bytes as the zmac build and start with the same
records, except BACKUP: zmac writes its 256 byte buffer HITBUF (at 4300H)
as zeros, MRAS leaves it out.
