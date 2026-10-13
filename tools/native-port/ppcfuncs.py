"""Guest functions from a ReXGlue generated/ folder: address -> instructions.

The generated C++ carries every PPC instruction as a comment; labels
(loc_XXXXXXXX:) give the address back after gaps.

    python ppcfuncs.py <generated/default> <out.json>
"""
import glob
import json
import os
import re
import sys

RE_DEF = re.compile(r"^DEFINE_REX_FUNC\(sub_([0-9A-F]{8})\)")
RE_LABEL = re.compile(r"^loc_([0-9A-F]{8}):")
RE_CALL = re.compile(r"\b(sub_[0-9A-F]{8}|__imp__\w+)\(ctx, base\)")


def parse(gen_dir):
    funcs = {}
    for path in sorted(glob.glob(os.path.join(gen_dir, "*_recomp.*.cpp"))):
        cur = None
        addr = 0
        for line in open(path, encoding="utf-8", errors="replace"):
            m = RE_DEF.match(line)
            if m:
                start = int(m.group(1), 16)
                cur = {"insns": [], "calls": [], "imports": []}
                funcs[start] = cur
                addr = start
                continue
            if cur is None:
                continue
            lm = RE_LABEL.match(line)
            if lm:
                addr = int(lm.group(1), 16)
                continue
            s = line.strip()
            if s.startswith("// ") and not s.startswith(("// PPC", "// FATAL", "// PARCHE")):
                text = s[3:]
                if re.match(r"^[a-z][a-z0-9.+-]*\b", text):
                    cur["insns"].append([addr, text])
                    addr += 4
                continue
            for c in RE_CALL.findall(s):
                if c.startswith("__imp__"):
                    cur["imports"].append(c[7:])
                else:
                    cur["calls"].append(int(c[4:], 16))
    return funcs


if __name__ == "__main__":
    f = parse(sys.argv[1])
    json.dump({f"{k:08X}": v for k, v in f.items()}, open(sys.argv[2], "w"))
    print(len(f), "functions")
