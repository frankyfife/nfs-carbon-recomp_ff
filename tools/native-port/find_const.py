"""Functions whose instructions mention given immediates (regex on the text).

    python find_const.py funcs.json LO HI PATTERN [PATTERN ...]

Prints functions in [LO, HI] that match every pattern, with the lines.
"""
import json
import re
import sys

funcs = {int(k, 16): v for k, v in json.load(open(sys.argv[1])).items()}
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
pats = [re.compile(p) for p in sys.argv[4:]]
for a in sorted(funcs):
    if not lo <= a <= hi:
        continue
    ins = funcs[a]["insns"]
    hits = [[(x, t) for x, t in ins if p.search(t)] for p in pats]
    if all(hits):
        print(f"sub_{a:08X} ({len(ins)} insns)")
        for h in hits:
            for x, t in h[:3]:
                print(f"    {x:08X} {t}")
