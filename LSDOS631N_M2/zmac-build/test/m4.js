// A minimal TRS-80 Model 4 for testing the LS-DOS hard disk image under
// Node: 64K RAM with the memory maps of port 84H (map 2: keyboard at
// F400H, video at F800H; map 3: all RAM), the keyboard matrix, the 30 Hz
// real time clock interrupt (IM 1, latch E0H, cleared by reading ECH),
// the CRTC cursor, and a WD1010 hard disk at C8H-CFH with 256 byte
// sectors (8 heads, 32 sectors per track). No floppy controller, no ROM:
// bootHd() does what the Model 4P / FreHD boot ROM does.

export const CPU_HZ = 4000000;

// Keyboard matrix: [row, bit] of each key, and the characters
const KEYS = {};
'@ABCDEFG'.split('').forEach((c, i) => KEYS[c] = [0, i]);
'HIJKLMNO'.split('').forEach((c, i) => KEYS[c] = [1, i]);
'PQRSTUVW'.split('').forEach((c, i) => KEYS[c] = [2, i]);
'XYZ'.split('').forEach((c, i) => KEYS[c] = [3, i]);
'01234567'.split('').forEach((c, i) => KEYS[c] = [4, i]);
'89:;,-./'.split('').forEach((c, i) => KEYS[c] = [5, i]);
KEYS['\r'] = [6, 0]; KEYS['\x03'] = [6, 2]; KEYS[' '] = [6, 7];
const SHIFTED = { '!': '1', '"': '2', '#': '3', '$': '4', '%': '5', '&': '6', "'": '7',
  '(': '8', ')': '9', '*': ':', '+': ';', '<': ',', '=': '-', '>': '.', '?': '/' };

export class Model4 {
  constructor(Z80, hdimg) {
    this.ram = new Uint8Array(0x10000);
    this.video = new Uint8Array(0x800).fill(32);
    this.opreg = 0;
    this.rows = new Uint8Array(8);		// keys down
    this.typing = []; this.phase = 0;
    this.mask = 0; this.latch = 0;		// interrupts (RTC is bit 2)
    this.crtc = new Uint8Array(16); this.crtcReg = 0;
    this.img = hdimg;
    this.hd = { sdh: 0, cyl: 0, sec: 0, status: 0x50, buf: null, ptr: 0, wr: false, off: 0 };
    const self = this;
    this.hal = {
      tStateCount: 0,
      readMemory: a => self.rd(a), writeMemory: (a, v) => self.wr(a, v),
      contendMemory() {}, contendPort() {},
      readPort: a => self.inp(a & 0xFF), writePort: (a, v) => self.outp(a & 0xFF, v),
    };
    this.z = new Z80(this.hal);
    this.z.reset();
    this.tick = CPU_HZ / 30;
    this.nextTick = this.tick;
  }

  map() { return this.opreg & 3; }
  rd(a) {
    if (this.map() === 2 && a >= 0xF400) {
      if (a >= 0xF800) return this.video[a - 0xF800];
      let v = 0;
      for (let r = 0; r < 8; r++) if (a & (1 << r)) v |= this.rows[r];
      return v;
    }
    return this.ram[a];
  }
  wr(a, v) {
    if (this.map() === 2 && a >= 0xF400) {
      if (a >= 0xF800) this.video[a - 0xF800] = v;
      return;
    }
    this.ram[a] = v;
  }

  // ---- WD1010, 256 byte sectors
  hdCmd(v) {
    const h = this.hd, c = v & 0xF0;
    if (c === 0x10 || c === 0x70) { h.status = (h.sdh & 0x18) ? 0x51 : 0x50; return; }
    const head = h.sdh & 7;
    const off = 256 + ((h.cyl * 8 + head) * 32 + h.sec) * 256;
    if ((h.sdh & 0x60) || (h.sdh & 0x18) || h.sec >= 32 || off + 256 > this.img.length) { h.status = 0x51; return; }
    h.ptr = 0; h.status = 0x58;
    if (c === 0x20) { h.buf = this.img.subarray(off, off + 256); h.wr = false; }
    else if (c === 0x30) { h.buf = new Uint8Array(256); h.wr = true; h.off = off; }
  }

  inp(p) {
    const h = this.hd;
    switch (p) {
      case 0xE0: return ~this.latch & 0xFF;		// active low
      case 0xEC: this.latch &= ~4; return 0xFF;	// clears the RTC interrupt
      case 0xF0: return 0x80;				// no floppy drive: not ready
      case 0xC8:
        if (h.buf && !h.wr && h.ptr < 256) {
          const v = h.buf[h.ptr++];
          if (h.ptr === 256) h.status = 0x50;
          return v;
        }
        return 0;
      case 0xC9: return 0;
      case 0xCF: return h.status;
    }
    return 0xFF;
  }

  outp(p, v) {
    const h = this.hd;
    switch (p) {
      case 0x84: this.opreg = v; return;
      case 0xE0: this.mask = v; return;
      case 0x88: this.crtcReg = v & 15; return;
      case 0x89: this.crtc[this.crtcReg] = v; return;
      case 0xC8:
        if (h.wr) {
          h.buf[h.ptr++] = v;
          if (h.ptr === 256) { this.img.set(h.buf, h.off); h.wr = false; h.status = 0x50; }
        }
        return;
      case 0xCB: h.sec = v; return;
      case 0xCC: h.cyl = (h.cyl & 0xFF00) | v; return;
      case 0xCD: h.cyl = (h.cyl & 0xFF) | (v << 8); return;
      case 0xCE: h.sdh = v; return;
      case 0xCF: this.hdCmd(v); return;
    }
  }

  // What the 4P / FreHD boot ROM does: cylinder 0 head 0 sector 1 to
  // 4300H, then jump there
  bootHd() {
    this.ram.set(this.img.subarray(256 + 256, 256 + 512), 0x4300);
    this.z.regs.pc = 0x4300;
    this.z.regs.sp = 0x4200;
    return true;
  }

  // Keys go down for two clock ticks and up for two
  key(ch) { this.typing.push(ch); }
  keyTick() {
    this.rows.fill(0);
    if (!this.typing.length) return;
    if (this.phase < 2) {
      let c = this.typing[0], shift = false;
      if (SHIFTED[c]) { c = SHIFTED[c]; shift = true; }
      const k = KEYS[c.toUpperCase()];
      if (k) this.rows[k[0]] |= 1 << k[1];
      if (shift) this.rows[7] |= 1;
    }
    if (++this.phase === 4) { this.phase = 0; this.typing.shift(); }
  }

  run(n) {
    const end = this.hal.tStateCount + n;
    while (this.hal.tStateCount < end) {
      this.z.step();
      if (this.hal.tStateCount >= this.nextTick) {
        this.nextTick += this.tick;
        this.latch |= 4;
        this.keyTick();
      }
      if ((this.latch & this.mask & 4) && this.z.regs.iff1) this.z.maskableInterrupt();
    }
  }

  text() {
    const rows = [];
    for (let y = 0; y < 24; y++) {
      let s = '';
      for (let x = 0; x < 80; x++) {
        const c = this.video[y * 80 + x] & 0x7F;
        s += c >= 32 && c < 127 ? String.fromCharCode(c) : ' ';
      }
      rows.push(s.replace(/ +$/, ''));
    }
    return rows.join('\n');
  }
}
