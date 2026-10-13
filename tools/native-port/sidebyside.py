"""Side-by-side diff of a MW and a Carbon guest function (numbers kept).

    python sidebyside.py mw.json carbon.json MW_ADDR CARBON_ADDR [max_lines]
"""
import difflib
import json
import re
import sys

RE_NUM = re.compile(r"-?0x[0-9a-fA-F]+|-?\b\d+\b")


def load(path):
    return {int(k, 16): v for k, v in json.load(open(path)).items()}


mw, cb = load(sys.argv[1]), load(sys.argv[2])
a, b = mw[int(sys.argv[3], 16)]["insns"], cb[int(sys.argv[4], 16)]["insns"]
limit = int(sys.argv[5]) if len(sys.argv) > 5 else 400
na = [RE_NUM.sub("#", t) for _, t in a]
nb = [RE_NUM.sub("#", t) for _, t in b]
sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
print(f"ratio {sm.ratio():.3f}  MW {len(a)}  Carbon {len(b)}")
n = 0
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    for k in range(max(i2 - i1, j2 - j1)):
        left = a[i1 + k] if i1 + k < i2 else None
        right = b[j1 + k] if j1 + k < j2 else None
        l = f"{left[0]:08X} {left[1]}" if left else ""
        r = f"{right[0]:08X} {right[1]}" if right else ""
        mark = " " if tag == "equal" and left[1] == right[1] else ("~" if tag == "equal" else "!")
        print(f"{mark} {l:46.46} | {r}")
        n += 1
        if n >= limit:
            sys.exit()
