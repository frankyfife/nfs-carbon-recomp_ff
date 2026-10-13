#!/usr/bin/env python3
"""Candidates for Carbon's 30 fps cap in OUR XEX build (docs/60fps.md).

Works on the loaded image (REX_DUMP_GUEST_IMAGE=1 writes guest_image.bin) with
a small PowerPC decoder, and optionally on generated/default for the kernel
imports each function calls. Prints, for checking by hand:

  1. float/double constants of the frame timing (1/30, 1/60, 30.0, 60.0, ...)
     and the code that loads them (lis + lfs/lfd/lwz);
  2. functions shaped like the engine's SetFPSLimiter(float fps): a short
     function that divides by f1 (fdivs) and stores the result to a global
     (LimitMinimumVideoTimeElapsed in the MW decomp), and their call sites
     with the fps they pass when it is a constant (30.0 = the cap);
  3. the D3D swap throttle argument (presentation interval << 16 | 10):
     0x0001000A interval 1, 0x0002000A interval 2;
  4. functions that read the time base (mftb: frame timing loops);
  5. with --generated: functions that call KeDelayExecutionThread and the
     wait imports (a time-based limiter sleeps), and their callers.

    python tools/find_60fps.py [--image guest_image.bin] [--init generated/default/nfscarbon_init.cpp]
                               [--generated generated/default]
"""
import argparse
import bisect
import glob
import os
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONSTANTS_F32 = {
    0x3D088889: "1/30",
    0x3C888889: "1/60",
    0x41F00000: "30.0",
    0x42700000: "60.0",
    0x3D888889: "2/30 (RealTimeElapsed default)",
    0x42055555: "33.333 (ms)",
    0x41855555: "16.667 (ms)",
    0x3E2AAAAB: "1/6 (FullSpeedMode step)",
    0x3991A2B4: "1/3600 (real time quantum)",
    0x45610000: "3600.0",
    0x47800000: "65536.0 (ms 16.16)",
}
CONSTANTS_F64_HI = {0x3FA11111: "1/30 (double)", 0x3F911111: "1/60 (double)",
                    0x403E0000: "30.0 (double)", 0x404E0000: "60.0 (double)"}
WAIT_IMPORTS = ("KeDelayExecutionThread", "NtDelayExecution", "KeWaitForSingleObject",
                "NtWaitForSingleObjectEx", "KeWaitForMultipleObjects", "VdSwap",
                "VdGetCurrentDisplayInformation", "KeQueryPerformanceCounter")


def s16(x):
    return x - 0x10000 if x & 0x8000 else x


def f32(word):
    return struct.unpack(">f", struct.pack(">I", word))[0]


class Image:
    def __init__(self, path, base):
        data = Path(path).read_bytes()
        data = data[: len(data) // 4 * 4]
        self.base = base
        self.words = struct.unpack(">%dI" % (len(data) // 4), data)

    def word(self, address):
        i = (address - self.base) // 4
        return self.words[i] if 0 <= i < len(self.words) else None

    def addresses(self):
        return range(self.base, self.base + 4 * len(self.words), 4)


def function_starts(image, init_path):
    if init_path and Path(init_path).exists():
        text = Path(init_path).read_text(errors="replace")
        return sorted({int(m, 16) for m in re.findall(r"\{\s*0x([0-9A-Fa-f]{8}),\s*sub_", text)})
    # Without the generated init table: after every blr and padding, and at
    # mflr r12 prologues.
    starts = {image.base}
    previous = None
    for a in image.addresses():
        w = image.word(a)
        if w == 0x4E800020:
            starts.add(a + 4)
        elif w == 0x7D8802A6 or (w and previous == 0):
            starts.add(a)
        previous = w
    return sorted(starts)


def enclosing(starts, address):
    i = bisect.bisect_right(starts, address) - 1
    return starts[i] if i >= 0 else None


def global_refs(image):
    """(address of the instruction, op, reg, target) for lis rX,hi + D-form use of rX."""
    refs = []
    hi = {}  # reg -> (value << 16, instruction index)
    for i, w in enumerate(image.words):
        op = w >> 26
        rd, ra = (w >> 21) & 31, (w >> 16) & 31
        if op == 15 and ra == 0:  # lis
            hi[rd] = ((w & 0xFFFF) << 16, i)
            continue
        if w == 0x4E800020:  # blr: a new function
            hi.clear()
            continue
        if op in (14, 32, 34, 36, 38, 40, 44, 48, 50, 52, 54) and ra in hi:
            value, at = hi[ra]
            if i - at <= 48:
                refs.append((image.base + 4 * i, op, rd, (value + s16(w & 0xFFFF)) & 0xFFFFFFFF))
        # Integer instructions that write rD end the tracking of that register.
        if op in (14, 15, 32, 34, 40, 42) and rd in hi:
            hi.pop(rd, None)
    return refs


OPS = {14: "addi", 32: "lwz", 34: "lbz", 36: "stw", 38: "stb", 40: "lhz", 44: "sth", 48: "lfs",
       50: "lfd", 52: "stfs", 54: "stfd"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=str(ROOT / "guest_image.bin"))
    ap.add_argument("--base", type=lambda s: int(s, 0), default=0x82000000)
    ap.add_argument("--init", default=str(ROOT / "generated/default/nfscarbon_init.cpp"))
    ap.add_argument("--generated", default=None, help="generated/default, for the imports")
    a = ap.parse_args()

    image = Image(a.image, a.base)
    starts = function_starts(image, a.init)
    refs = global_refs(image)
    by_target = defaultdict(list)
    for at, op, reg, target in refs:
        by_target[target].append((at, op, reg))
    print(f"image {4 * len(image.words):#x} bytes at {a.base:#010x}, {len(starts)} functions, "
          f"{len(refs)} lis-based references\n")

    # 1. Constants that code loads.
    print("== 1. timing constants loaded by code (address: value, loads)")
    for address in image.addresses():
        w = image.word(address)
        name = CONSTANTS_F32.get(w)
        if not name and w in CONSTANTS_F64_HI and image.word(address + 4) is not None:
            name = CONSTANTS_F64_HI[w]
        if not name or address not in by_target:
            continue
        loads = by_target[address]
        sites = ", ".join(f"{at:08X} {OPS.get(op, op)} in sub_{enclosing(starts, at):08X}"
                          for at, op, _ in loads[:6])
        more = f" (+{len(loads) - 6})" if len(loads) > 6 else ""
        print(f"  {address:08X}: {name:30} {sites}{more}")

    # 2. SetFPSLimiter shape: fdivs fD,fA,f1 and stfs fD to a global, in a short function.
    print("\n== 2. SetFPSLimiter-shaped functions (fdivs by f1, stored to a global)")
    stores = {at: target for at, op, _, target in refs if op == 52}
    limiters = {}
    for i, w in enumerate(image.words):
        if w >> 26 != 59 or (w >> 1) & 31 != 18 or (w >> 11) & 31 != 1:
            continue
        at = a.base + 4 * i
        start = enclosing(starts, at)
        if start is None:
            continue
        k = bisect.bisect_right(starts, start)
        end = starts[k] if k < len(starts) else start + 0x400
        if end - start > 0x60:
            continue
        fd = (w >> 21) & 31
        for k in range(1, 8):
            x = image.word(at + 4 * k)
            if x is not None and x >> 26 == 52 and (x >> 21) & 31 == fd and at + 4 * k in stores:
                limiters[start] = stores[at + 4 * k]
                break
    for start, target in sorted(limiters.items()):
        value = image.word(target)
        print(f"  sub_{start:08X}: writes {target:08X} (now {value:08X} = {f32(value):.6f})"
              if value is not None else f"  sub_{start:08X}: writes {target:08X}")
    # Call sites, with a constant f1 when it is loaded just before.
    f1_loads = {at: target for at, op, reg, target in refs if op == 48 and reg == 1}
    for i, w in enumerate(image.words):
        if w >> 26 != 18 or w & 3 != 1:
            continue
        at = a.base + 4 * i
        li = w & 0x03FFFFFC
        callee = (at + (li - 0x04000000 if li & 0x02000000 else li)) & 0xFFFFFFFF
        if callee not in limiters:
            continue
        fps = "?"
        for k in range(1, 12):
            if at - 4 * k in f1_loads:
                v = image.word(f1_loads[at - 4 * k])
                fps = f"{f32(v):g}" if v is not None else "?"
                break
        flag = "   <-- 30 fps cap?" if fps == "30" else ""
        print(f"    call at {at:08X} in sub_{enclosing(starts, at):08X}: fps {fps}{flag}")

    # 3. Swap throttle argument.
    print("\n== 3. presentation interval << 16 | 10 (lis rX,N + ori rX,rX,10)")
    for i, w in enumerate(image.words[:-4]):
        if w >> 26 != 15 or (w >> 16) & 31 or (w & 0xFFFF) not in (1, 2):
            continue
        rd = (w >> 21) & 31
        for k in range(1, 4):
            x = image.words[i + k]
            if x >> 26 == 24 and (x >> 21) & 31 == rd and (x >> 16) & 31 == rd and x & 0xFFFF == 10:
                at = a.base + 4 * i
                print(f"  {at:08X} in sub_{enclosing(starts, at):08X}: interval {w & 0xFFFF}")

    # 4. Time base readers.
    print("\n== 4. functions that read the time base (mftb)")
    mftb = sorted({enclosing(starts, a.base + 4 * i) for i, w in enumerate(image.words)
                   if w & ~(31 << 21) == 0x7C0C42E6} - {None})
    print("  " + " ".join(f"sub_{s:08X}" for s in mftb))

    # 5. Imports, from the generated C++.
    if a.generated:
        sys.path.insert(0, str(ROOT / "tools/native-port"))
        import ppcfuncs
        funcs = ppcfuncs.parse(a.generated)
        callers = defaultdict(set)
        for start, f in funcs.items():
            for c in f["calls"]:
                callers[c].add(start)
        print("\n== 5. callers of the wait and timing imports (and their callers)")
        for name in WAIT_IMPORTS:
            users = sorted(s for s, f in funcs.items() if name in f["imports"])
            for s in users:
                up = " ".join(f"sub_{c:08X}" for c in sorted(callers[s])[:8])
                print(f"  {name}: sub_{s:08X} ({len(funcs[s]['insns'])} insns) <- {up}")


if __name__ == "__main__":
    sys.exit(main())
