#!/usr/bin/env python3
#
#	build.py [hd] [floppy] [--zmac ZMAC] [--out DIR]
#
#	Assemble LS-DOS 6.3.1 for the Model II with zmac (George Phillips,
#	https://github.com/gp48k/zmac) instead of MRAS under emulation.
#
#	hd	@HD on: out/hd/lsdos631n-hd.hdv, a hard disk image that boots
#		from the hard disk boot ROM (drive :0 the hard disk, the
#		floppies :1 and :2), and its files in out/hd/files
#	floppy	@HD off, the normal floppy system: its files in out/floppy,
#		ready for ZGET2.BAT to put on a boot floppy
#
#	Without hd or floppy it builds both. The sources in ../lsdos631 are
#	copied to work/<variant> with Unix line ends; BUILDVER/ASM there gets
#	@HD set for hd. The sources stay as MRAS wants them: in the copies a
#	few spellings zmac does not take are changed (EDITS), and each module
#	starts with PRELUDE, macros standing in for what zmac lacks. Then:
#
#	LOWCORE (BOOT/SYS), SYSRES (SYS0), SYS1-SYS13, the library commands
#	and SYS6-SYS8 built from them as BLDLIBS/CMD does (mklib.py), the
#	utilities, and for hd the loader HDBOOT2/ASM and the disk
#	(mklsdos.py).
#
#	zmac: --zmac, else $ZMAC, else zmac on the PATH, else it is cloned
#	and built in work/zmac (or zmac.exe from there on Windows).
#
import argparse, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, '..', 'lsdos631'))
sys.path.insert(0, HERE)
import mklib, mklsdos

ZMAC_URL = 'https://github.com/gp48k/zmac'

# zmac stand-ins for MRAS, put in front of each module: COM (a comment
# record in the /CMD file) does nothing, and LORG (load somewhere else
# than the code runs) is done with PHASE/DEPHASE. MRAS keeps the load
# offset over later ORGs, which zmac does not allow inside PHASE, so ORG
# is a macro too (.ORG is still the built-in one). ZM$OFS is the load
# address minus the run address.
PRELUDE = '''; ZMPRE/ASM - zmac stand-ins for MRAS (written by build.py)
ZM$OFS	DEFL	0
ZM$PH	DEFL	0
COM	MACRO	#QQS
	ENDM
ORG	MACRO	#QQA
ZM$ADR	DEFL	#QQA
	IF	ZM$PH
	DEPHASE
ZM$PH	DEFL	0
	ENDIF
	.ORG	ZM$ADR+ZM$OFS
	IFNE	ZM$OFS,0
	PHASE	ZM$ADR
ZM$PH	DEFL	-1
	ENDIF
	ENDM
LORG	MACRO	#QQL
ZM$ADR	DEFL	#QQL
ZM$RUN	DEFL	$
	IF	ZM$PH
	DEPHASE
ZM$PH	DEFL	0
	ENDIF
ZM$OFS	DEFL	ZM$ADR-ZM$RUN
	.ORG	ZM$ADR
	IFNE	ZM$OFS,0
	PHASE	ZM$RUN
ZM$PH	DEFL	-1
	ENDIF
	ENDM
'''

# Spellings zmac does not take, changed in the copies (same code):
# (file, old, new[, 'all'])
EDITS = [
	('svcequ.asm', "NUL\tEQU\t0\t", ";NUL\tEQU\t0\t"),	# NUL: an operator in zmac, not used
	('sys3.asm', "\tELSE\t\t\t:<--> Before", "\tELSE\t\t\t;<--> Before"),	# a colon for a semicolon
	('libcmds/lblist.asm', "\tCALL\tLIST\n", "\tCALL\tLISTF\n"),	# LIST is a pseudo-op in zmac
	('libcmds/lblist.asm', "\nLIST\tCALL\tRESKFL", "\nLISTF\tCALL\tRESKFL"),
	('utils/diskcopy.asm', "\tDC\t11,-18", "\tDC\t11,0EEH"),
	('utils/memdisk.asm', "(IX+0FFH)", "(IX-1)", 'all'),
	('utils/com.asm', "CLDATA$\tDB\t0", "\tDB\t0"),	# defined twice, same value
]

# Library commands (see ../lsdos631/other/l631lib?.dat)
LIBCMDS = ('lbmemory lbdir lbcopy lblib lbremove lbrename lbdevice lbroute '
	'lblink lbreset lbset lblist lbdo lbload lbfree lbdate lbdebug lbattrib '
	'lbpurge lbdump lbcreate lbauto lbbuild lbsystem lbsysgen lbforms '
	'lbsetcom lbsetki lbspool').split()

# Utilities (as ../lsdos631/other/buildutl.jcl): source, file name
UTILS = [('backup', 'BACKUP/CMD'), ('click', 'CLICK/FLT'), ('com', 'COM/DVR'),
	('comm', 'COMM/CMD'), ('conv', 'CONV/CMD'), ('dateconv', 'DATECONV/CMD'),
	('diskcopy', 'DISKCOPY/CMD'), ('floppy', 'FLOPPY/DCT'),
	('format', 'FORMAT/CMD'), ('forms', 'FORMS/FLT'), ('help', 'HELP/CMD'),
	('ksm', 'KSM/FLT'), ('log', 'LOG/CMD'), ('memdisk', 'MEMDISK/DCT'),
	('patch', 'PATCH/CMD'), ('repair', 'REPAIR/CMD')]
# Not on the hard disk: CONV (Model III disks) and FLOPPY/DCT
HD_SKIP = ('conv', 'floppy')

NOTICE = '''LS-DOS 6.3.1 for the TRS-80 Model II, level N.

The permission statement from Tim Mann's web page says the following
about the MISOSYS software available for download:

Roy Soltoff holds the copyright to the software and documentation in
the list below; notices that name other authors are outdated. Roy
grants free permission to everyone to download and use this software
and documentation and to redistribute it to others, provided this
notice is retained. All other rights are reserved.

Copyright 1982-1984, 1986, 1990 by MISOSYS, Inc.
Typed in (and enhanced) by Pete Cervasio. Changes are copyright
1997-98 Peter W. Cervasio. Permission to do whatever you want with my
changes is granted, as long as my copyright notice is left intact.

Model II build, level N: Michel Bernard (GmEsoft),
https://github.com/GmEsoft/TRS80_M2_LSDOS631N
Hard disk boot and zmac build:
https://github.com/bhemstra/TRS80_M2_LSDOS631N
'''


def run(*cmd, **kw):
	subprocess.run(cmd, check=True, **kw)


def find_zmac(arg, work):
	z = arg or os.environ.get('ZMAC') or shutil.which('zmac')
	if z:
		return os.path.abspath(z)
	d = os.path.join(work, 'zmac')
	if not os.path.isdir(d):
		run('git', 'clone', '-q', '--depth', '1', ZMAC_URL, d)
	if os.name == 'nt':
		return os.path.join(d, 'zmac.exe')
	z = os.path.join(d, 'src', 'zmac')
	if not os.path.isfile(z):
		run('make', '-s', '-C', os.path.join(d, 'src'), 'zmac')
	return z


def prepare(dst, hd):
	"""Copy the sources with LF line ends and set the switches. zmac looks
	for *GET NAME as NAME.asm, so each file also gets an upper case name
	(on a case sensitive file system), and libcmds/ and utils/ see the
	top level sources."""
	if os.path.isdir(dst):
		shutil.rmtree(dst)
	for rel in ('.', 'libcmds', 'utils'):
		os.makedirs(os.path.join(dst, rel))
		for f in os.listdir(os.path.join(SRC, rel)):
			if f.lower().endswith('.asm'):
				t = open(os.path.join(SRC, rel, f), 'rb').read()
				t = t.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
				open(os.path.join(dst, rel, f.lower()), 'wb').write(t)
	p = os.path.join(dst, 'buildver.asm')
	s = open(p).read()
	s, n = re.subn(r'^(@HD\s+EQU\s+)\S+', r'\g<1>%d' % (-1 if hd else 0), s, flags=re.M)
	if n != 1:
		sys.exit('buildver.asm: no @HD switch')
	open(p, 'w').write(s)
	for path, old, new, *all in EDITS:
		p = os.path.join(dst, path)
		s = open(p).read()
		if old not in s:
			sys.exit('%s: text to change not found: %r' % (path, old))
		open(p, 'w').write(s.replace(old, new, -1 if all else 1))
	# The modules start with the prelude (not the files they *GET)
	mods = ['lowcore', 'sysres', 'hdboot2'] + ['sys%d' % n for n in (1, 2, 3, 4, 5, 9, 10, 11, 12, 13)]
	mods = [('.', m) for m in mods] + [('libcmds', m) for m in LIBCMDS] + [('utils', m) for m, _ in UTILS]
	for rel, m in mods:
		p = os.path.join(dst, rel, m + '.asm')
		s = open(p).read()
		open(p, 'w').write('*GET\tZMPRE\n' + s)
	open(os.path.join(dst, 'zmpre.asm'), 'w').write(PRELUDE)

	def link(src, dstf):
		if os.path.exists(dstf):
			return
		try:
			os.symlink(src, dstf)
		except OSError:
			shutil.copy(os.path.join(os.path.dirname(dstf), src), dstf)

	top = sorted(f for f in os.listdir(dst) if f.endswith('.asm'))
	for rel in ('libcmds', 'utils'):
		for f in top:
			link(os.path.join('..', f), os.path.join(dst, rel, f))
	for rel in ('.', 'libcmds', 'utils'):
		d = os.path.join(dst, rel)
		for f in sorted(os.listdir(d)):
			if f.endswith('.asm') and f == f.lower():
				link(f, os.path.join(d, f[:-4].upper() + '.asm'))


def mkequ(lst, out):
	"""The equates of a listing's symbol table, as XREF (EQU) makes them"""
	t = open(lst, errors='replace').read().split('Symbol Table:')[1]
	with open(out, 'w') as o:
		for line in t.splitlines():
			m = re.match(r'^(\S+)\s+=?\s*([0-9A-Fa-f]+)\s+(-?\d+)\s*$', line)
			if m and m.group(1)[0] not in '?$':
				o.write('%s\tEQU\t%s\n' % (m.group(1), m.group(3)))
		o.write('\tEND\n')


def assemble(zmac, d, name, equs):
	"""Assemble d/name.asm into d/out/name.cmd (and .cim, .lst). The .EQU
	files go next to it. MRAS lets a module define a symbol an .EQU file
	has too, zmac does not: such symbols are dropped from the copies (or,
	when two .EQU files have one, from the later one)."""
	out = os.path.join(d, 'out')
	os.makedirs(out, exist_ok=True)
	eq = {e: open(e).read().splitlines() for e in equs}
	for _ in range(10):
		for e, lines in eq.items():
			open(os.path.join(d, os.path.basename(e)), 'w').write('\n'.join(lines) + '\n')
		r = subprocess.run([zmac, '--mras', '-o', 'out/%s.cmd' % name, '-o', 'out/%s.cim' % name,
			'-o', 'out/%s.lst' % name, name + '.asm'], cwd=d, capture_output=True, text=True)
		if r.returncode == 0:
			return os.path.join(out, name)
		err = (r.stdout + r.stderr).splitlines()
		dropped = False
		for i, l in enumerate(err[:-1]):
			if 'Mult. def.' not in l or not err[i + 1].strip():
				continue
			sym = err[i + 1].split()[0]
			where = l.split('(')[0]
			for e in eq:
				if where.endswith('.EQU') and os.path.basename(e) != where:
					continue
				n = len(eq[e])
				eq[e] = [x for x in eq[e] if x.split('\t')[0] != sym]
				dropped |= len(eq[e]) != n
		if not dropped:
			sys.exit('%s/%s.asm:\n%s' % (d, name, '\n'.join(err[:20])))
	sys.exit(name + ': too many duplicate symbols')


def build(zmac, work, hd):
	"""Assemble one variant, return the files: (LS-DOS name, path)"""
	src = os.path.join(work, 'hd' if hd else 'floppy')
	prepare(src, hd)
	equ = lambda n: os.path.join(src, 'equ', n + '.EQU')
	os.makedirs(os.path.join(src, 'equ'))

	lowcore = assemble(zmac, src, 'lowcore', [])
	mkequ(lowcore + '.lst', equ('LOWCORE'))
	sysres = assemble(zmac, src, 'sysres', [equ('LOWCORE')])
	mkequ(sysres + '.lst', equ('SYSRES'))
	eqs = [equ('LOWCORE'), equ('SYSRES')]
	files = [('BOOT/SYS', lowcore + '.cim'), ('SYS0/SYS', sysres + '.cmd')]
	for n in (1, 2, 3, 4, 5):
		files.append(('SYS%d/SYS' % n, assemble(zmac, src, 'sys%d' % n, eqs) + '.cmd'))
	mkequ(os.path.join(src, 'out', 'sys5.lst'), equ('SYS5'))
	eqs.append(equ('SYS5'))
	for n in (9, 10, 11, 12, 13):
		files.append(('SYS%d/SYS' % n, assemble(zmac, src, 'sys%d' % n, eqs) + '.cmd'))

	lib = os.path.join(src, 'libcmds')
	for n in LIBCMDS:
		assemble(zmac, lib, n, eqs)
	for n in (6, 7, 8):
		f = os.path.join(src, 'out', 'sys%d.cmd' % n)
		mklib.build(f, os.path.join(SRC, 'other', 'l631lib%d.dat' % n), os.path.join(lib, 'out'))
		files.append(('SYS%d/SYS' % n, f))
	ut = os.path.join(src, 'utils')
	for n, fname in UTILS:
		if not (hd and n in HD_SKIP):
			files.append((fname, assemble(zmac, ut, n, eqs) + '.cmd'))
	if hd:
		files.append(('HDBOOT2', assemble(zmac, src, 'hdboot2', [equ('LOWCORE')]) + '.cim'))
	return files


# How the MRAS build names its output (see ../lsdos631/other/getnew.jcl)
def hostname(lsname, path):
	if lsname == 'BOOT/SYS':
		return 'lowcore.cim'
	n, _, e = lsname.lower().partition('/')
	return n + '.' + ('cmd' if e == 'sys' else e)


def main():
	ap = argparse.ArgumentParser(description='Build LS-DOS 6.3.1 for the Model II with zmac')
	ap.add_argument('variant', nargs='*', choices=['hd', 'floppy'], help='default: both')
	ap.add_argument('--zmac', help='zmac binary')
	ap.add_argument('--out', default=os.path.join(HERE, 'out'))
	args = ap.parse_args()
	variants = args.variant or ['hd', 'floppy']
	work = os.path.join(HERE, 'work')
	os.makedirs(work, exist_ok=True)
	zmac = find_zmac(args.zmac, work)

	for v in variants:
		files = build(zmac, work, v == 'hd')
		out = os.path.join(args.out, v if v == 'floppy' else os.path.join('hd', 'files'))
		if os.path.isdir(out):
			shutil.rmtree(out)
		os.makedirs(out)
		for lsname, path in files:
			shutil.copy(path, os.path.join(out, hostname(lsname, path)))
		if v == 'floppy':
			# The job that puts these on a floppy, see ZGET2.BAT
			t = open(os.path.join(HERE, 'zget2.jcl'), 'rb').read()
			open(os.path.join(out, 'zget2.jcl'), 'wb').write(t)
			print('floppy: files in', out)
			continue
		notice = os.path.join(out, 'notice.txt')
		open(notice, 'wb').write(NOTICE.replace('\n', '\r').encode())
		d = dict(files)
		ondisk = [(n, p) for n, p in files if n not in ('BOOT/SYS', 'SYS0/SYS', 'HDBOOT2')]
		img = os.path.join(args.out, 'hd', 'lsdos631n-hd.hdv')
		mklsdos.build(img, d['BOOT/SYS'], d['SYS0/SYS'], d['HDBOOT2'],
			[('SYS0/SYS', d['SYS0/SYS'])] + ondisk + [('NOTICE/TXT', notice)])
		print('hd: image', img)


main()
