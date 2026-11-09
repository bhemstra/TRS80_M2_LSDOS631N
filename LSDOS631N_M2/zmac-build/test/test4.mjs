// test4.mjs [image] : boot the Model 4 LS-DOS hard disk image on the
// minimal Model 4 of m4.js, answer the date and time, look at the disk,
// write files and check they are still there after booting again.
import { readFileSync } from 'fs';
import { Z80 } from './z80.js';
import { Model4, CPU_HZ } from './m4.js';

const img = new Uint8Array(readFileSync(process.argv[2] ||
  new URL('../out/m4/hd/lsdos631n-m4-hd.hdv', import.meta.url)));
let fails = 0;

// Boot, then type each line when LS-DOS waits for one; the screen after
function session(lines) {
  const m = new Model4(Z80, img);
  m.bootHd();
  let i = 0, idle = 0;
  for (let t = 0; t < 3000 && i <= lines.length; t++) {
    m.run(CPU_HZ / 10);
    const last = m.text().split('\n').filter(x => x.trim()).pop() || '';
    if (/(Ready|\?) *_? *$/.test(last) && !m.typing.length) {
      if (++idle < 3) continue;		// let it settle
      idle = 0;
      if (i === lines.length) break;
      for (const c of lines[i++] + '\r') m.key(c);
    } else idle = 0;
  }
  return m.text();
}

function expect(screen, what, re) {
  const ok = re.test(screen);
  console.log((ok ? 'ok   ' : 'FAIL ') + what);
  if (!ok) { fails++; console.log(screen); }
}

let s = session(['11/09/26', '12:00:00', 'DEVICE', 'FREE']);
expect(s, 'boots to LS-DOS Ready', /LS-DOS Ready/);
expect(s, 'drive 0 is the hard disk', /:0 +\[LSDOS-HD\] .*Rigid.*Cyls=202, Fixed/);
expect(s, 'floppies are :1 and :2', /:1 .*Floppy #1[\s\S]*:2 .*Floppy #2/);
expect(s, 'FREE sees 6464K', /Free Space = +[\d.]+K\/ 6464\.00K/);

s = session(['11/09/26', '12:00:00',
  "DUMP TEST/CMD (START=X'3000',END=X'3FFF',TRA=X'402D')",
  'COPY TEST/CMD COPY/CMD', 'DIR /CMD']);
expect(s, 'DUMP and COPY write files', /COPY\/CMD[\s\S]*TEST\/CMD/i);
s = session(['11/09/26', '12:00:00', 'DIR /CMD']);
expect(s, 'the files are there after booting again', /COPY\/CMD[\s\S]*TEST\/CMD/i);
expect(s, 'BACKUP, FORMAT and the other utilities are there', /BACKUP\/CMD[\s\S]*FORMAT\/CMD/i);
s = session(['11/09/26', '12:00:00', 'LIST NOTICE/TXT']);
expect(s, 'LIST reads a file', /Roy Soltoff|permission|MISOSYS/i);
process.exit(fails ? 1 : 0);
