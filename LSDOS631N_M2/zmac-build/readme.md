Building LS-DOS with zmac
=========================

This directory contains the files needed to build LS-DOS 6.3.1 level N
for the Model II (and the Model 4) from the sources in `../lsdos631` with
[zmac](https://github.com/gp48k/zmac) (George Phillips) on the host,
instead of MRAS inside trs80gp. It makes:

- **a hard disk that boots by itself**: `out/hd/lsdos631n-hd.hdv`, for a
  Model II (or 12, 16, 6000) with a hard disk boot ROM, trs80gp or FreHD.
  Drive `:0` is the hard disk, the floppy drives are `:1` and `:2`.
- **the normal floppy system**: its files in `out/floppy`, which
  `ZGET2.BAT` puts on a boot floppy in trs80gp, like `GET2_NEW.BAT` does
  with the MRAS build.
- with `--model 4`, the same for the **Model 4**: a hard disk image
  `out/m4/hd/lsdos631n-m4-hd.hdv` that a Model 4P, or a Model 4 with the
  FreHD auto boot ROM, boots from (drive `:0` the hard disk, the floppy
  drives `:1` to `:3`), and the floppy system's files in `out/m4/floppy`.

| File          | Contents                                                     |
|---------------|--------------------------------------------------------------|
| `build.py`    | assembles everything, makes the hard disk image              |
| `mklib.py`    | builds SYS6/SYS7/SYS8 from the library commands, as BLDLIBS/CMD does |
| `mklsdos.py`  | writes the hard disk image: boot area, GAT, HIT, directory, files |
| `ZGET2.BAT`, `zget2.jcl` | put the floppy build on `L631NEW2.DSK` in trs80gp |
| `test/`       | `test.mjs` boots the Model II hard disk image in a Model II emulator under Node (`m2.js`); `test4.mjs` the Model 4 one in a minimal Model 4 (`m4.js`) |

Building
--------

Needs Python 3 and zmac. `build.py` takes zmac from `--zmac`, `$ZMAC` or
the PATH, or else clones and builds it in `work/zmac` (git, make and a C
compiler; on Windows it uses the `zmac.exe` from that clone).

    python3 build.py            # both
    python3 build.py hd         # only the hard disk image
    python3 build.py floppy     # only the floppy system
    python3 build.py --model 4  # the same for the Model 4, in out/m4

The Model 4 build sets `@MOD4` and clears `@MOD2` in its copy of
`BUILDVER/ASM`; it makes BOOT/SYS (`lowcore.cim`), SYS0-SYS13 and all
utilities of `BUILDUTL/JCL` (TAPE100 too).

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

Testing the hard disk images:

    node test/test.mjs
    node test/test4.mjs

They boot the image, answer the date and time, check the drives (DEVICE,
FREE), write files with DUMP and COPY, boot again and read them back.
`test/m4.js` is just enough of a Model 4 for that: memory maps, keyboard
matrix, video, the clock interrupt and the hard disk; no floppy drives.

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

- `lowcore.asm`: DCT 0 is the hard disk (`hddvr2.asm`, for both models,
  put after the floppy driver in the space for drivers below 1200H); the
  physical floppy drives follow from `:1` (Model II: 0 and 1 as `:1` and
  `:2`; Model 4: 0 and 1 as `:1` and `:2`).
- `sysinit4.asm`: SYSINIT leaves DCT 0 alone instead of setting it up
  from what the floppy boot sector left.
- `hdboot2.asm` (Model II) or `hdboot4.asm` (Model 4) is the loader the
  boot ROM starts.
- `utils/format2.asm` (Model 4): FORMAT takes the default cylinder counts
  of the drives from the DCTs at 0470H as they are on drive 0 cylinder 0.
  On a floppy that is sector 2; on the hard disk the boot area holds the
  memory from 0000H on, so it is sector 6.

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

### Model 4

The Model 4 drive has 256 byte sectors (8 heads, 32 sectors per track,
101 cylinders, 6.6 MB), so each LS-DOS sector is a whole one; the LS-DOS
layout is the same (202 cylinders of 4 heads, cylinder 0 BOOT/SYS,
cylinder 1 the directory). The image header has the FreHD auto boot flags
(byte 8 = 01H, byte 11 = 02H).

The Model 4P boot ROM and the FreHD auto boot ROM read cylinder 0 head 0
sector 1 into 4300H and jump to it. Counted from head 0 sector 0 on
through the heads of cylinder 0:

| Sector | Contents                                                      |
|--------|---------------------------------------------------------------|
| 1      | `hdboot4.asm` (byte 2 is the directory cylinder, as in a floppy boot sector) |
| 2-37   | memory 0000H-23FFH: lowcore with SYS0 loaded on top           |
| 38-45  | video memory F800H-FFFFH                                      |

The loader does what the Fuzix Model 4 hard disk loader does that runs on
a FreHD: reset the controller, memory map 86H, external I/O bus on (port
ECH), controller enable; then it loads the sectors, sets the disk hooks,
the jump at the NMI vector 66H (the floppy driver ends its transfers with
an NMI), OPREG$ and the CRTC as the floppy BOOT/SYS does, and starts
SYSINIT. It
fits in one sector and makes no CALLs.

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
  and a `:` for a `;` in `sys3.asm`; for the Model 4 `DB 0-SNDOFF` (a
  negative byte) in `sound.asm`.
- writes two character constants as MRAS reads them: MRAS takes `'IK'`
  as `'I'*256+'K'`, zmac the other way round, so `LD DE,'IK'` becomes
  `LD DE,'I'<+8!'K'` (in SYSINIT for the Model 4, COM, FORMS, HELP,
  MEMDISK and seven library commands).
- makes `lowcore.cim` as MRAS `-CI` does: the bytes in the order they
  are assembled, DS space filled but nothing for an ORG, so the Model 4
  boot sector (ORG 4300H) follows page 2.

Status
------

The Model II hard disk image works in the emulator of `test/` (and the
browser version it comes from), the Model 4 one in the minimal Model 4 of
`test/m4.js`; neither has run in trs80gp, xtrs or on real hardware yet.
`ZGET2.BAT` has not been run.

MRAS 1.1a, XREF and BLDLIBS (from `../lsdos631/tools` and `other`), run
under LS-DOS in that emulator on these sources, build the same set for
the Model II and the Model 4 (`@HD` off and on): LOWCORE, SYS0-SYS13, the
29 library commands, SYS6-SYS8 and the utilities. Everything matches the
zmac build byte for byte (BOOT/SYS and the libraries as files, the /CMD
files in what they load and their records), except BACKUP: zmac writes
its 256 byte buffer HITBUF as zeros, MRAS leaves it out.

For the Model 4, MRAS used to fail on SYSRES: the local labels `$?1`-`$?3`
in `sound.asm` became `$A1`-`$A3`, which LOWCORE/EQU (made by XREF) has
too, so a branch went wrong and the end of SYS0 was lost. They are now
SNDGO, SNDNOT and SNDTON (same code; zmac was not affected, as `build.py`
leaves the `$` labels out of the `.EQU` files). (`utils/conv2.asm` has LF line ends where the others have
CR; IMPORT2 -N takes care of that in the MRAS flow.)
