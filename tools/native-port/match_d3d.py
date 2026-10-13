"""Matches the Xbox D3D library functions of NFS Most Wanted to NFS Carbon.

Both games link the XDK's D3D statically and without symbols. The library is
found in each as the address block around the functions that call Vd* kernel
imports (as tools/renderprobe/d3d_layer.py of the MW project does). Functions
are compared by their instruction sequence with all numbers blanked out
(struct offsets and addresses differ between the two builds), and matched in
address order, since both libraries keep the same layout.

    python match_d3d.py mw.json carbon.json out.json
"""
import difflib
import json
import re
import sys

RE_NUM = re.compile(r"-?0x[0-9a-fA-F]+|-?\b\d+\b")


def norm(text):
    return RE_NUM.sub("#", text)


def load(path):
    raw = json.load(open(path))
    return {int(k, 16): v for k, v in raw.items()}


def d3d_block(funcs):
    addrs = sorted(funcs)
    callers = {}
    for a, f in funcs.items():
        for c in f["calls"]:
            callers.setdefault(c, set()).add(a)
    seeds = [a for a, f in funcs.items() if any(i.startswith("Vd") for i in f["imports"])]
    lo, hi = min(seeds), max(seeds)
    # Vd* callers outside a dense block (the game's own video code) widen it
    # too much; keep the densest cluster: seeds within 0x40000 of the median.
    seeds.sort()
    med = seeds[len(seeds) // 2]
    near = [s for s in seeds if abs(s - med) < 0x40000]
    lo, hi = min(near), max(near)
    changed = True
    while changed:
        changed = False
        inside = [a for a in addrs if lo <= a <= hi]
        i_lo, i_hi = addrs.index(inside[0]), addrs.index(inside[-1])
        inset = set(inside)
        for idx in (i_lo - 1, i_hi + 1):
            if not 0 <= idx < len(addrs):
                continue
            a = addrs[idx]
            if any(c in inset for c in funcs[a]["calls"]) or callers.get(a, set()) & inset:
                lo, hi = min(lo, a), max(hi, a)
                changed = True
    return lo, hi


def seq(f):
    return [norm(t) for _, t in f["insns"]]


def main():
    mw, cb = load(sys.argv[1]), load(sys.argv[2])
    mlo, mhi = d3d_block(mw)
    clo, chi = d3d_block(cb)
    print(f"MW block {mlo:08X}-{mhi:08X}, Carbon block {clo:08X}-{chi:08X}")
    m_list = [a for a in sorted(mw) if mlo <= a <= mhi]
    # Carbon's library may be a newer XDK with extra functions: search a margin.
    c_list = [a for a in sorted(cb) if clo - 0x8000 <= a <= chi + 0x8000]
    c_seq = {a: seq(cb[a]) for a in c_list}
    print(f"{len(m_list)} MW functions, {len(c_list)} Carbon candidates")
    result = {}
    last_idx = 0
    for a in m_list:
        s = seq(mw[a])
        best = (0.0, None, None)
        # Prefer candidates after the previous match (same layout).
        for i, c in enumerate(c_list):
            cs = c_seq[c]
            if not cs or abs(len(cs) - len(s)) > max(8, len(s) // 3):
                continue
            sm = difflib.SequenceMatcher(None, s, cs, autojunk=False)
            if sm.real_quick_ratio() < best[0] or sm.quick_ratio() < best[0]:
                continue
            r = sm.ratio()
            if i < last_idx:
                r -= 0.02
            if r > best[0]:
                best = (r, c, i)
        if best[1] is not None:
            result[f"{a:08X}"] = {"carbon": f"{best[1]:08X}", "ratio": round(best[0], 3),
                                  "mw_insns": len(s), "carbon_insns": len(c_seq[best[1]])}
            if best[0] > 0.9:
                last_idx = best[2]
    json.dump(result, open(sys.argv[3], "w"), indent=1)
    good = sum(1 for v in result.values() if v["ratio"] >= 0.9)
    print(f"matched {len(result)}, ratio >= 0.9: {good}")


if __name__ == "__main__":
    main()
