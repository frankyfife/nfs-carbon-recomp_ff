"""Finds Carbon's counterparts of MW D3D functions through their callers.

The game code around the D3D library (EA's engine) is far more alike between
NFS Most Wanted and NFS Carbon than the library itself (a newer XDK in
Carbon). Callers are matched by their instruction sequence with numbers
blanked (exact match first, then by similarity among functions of the same
size); at the same call position the matched Carbon caller calls the Carbon
counterpart. Votes over all callers decide.

    python match_by_callers.py mw.json carbon.json MW_ADDR [MW_ADDR ...]
"""
import collections
import difflib
import hashlib
import json
import re
import sys

RE_NUM = re.compile(r"-?0x[0-9a-fA-F]+|-?\b\d+\b")


def load(path):
    return {int(k, 16): v for k, v in json.load(open(path)).items()}


def key(f):
    return hashlib.sha1("\n".join(RE_NUM.sub("#", t) for _, t in f["insns"]).encode()).hexdigest()


def call_sites(f):
    """Ordered direct call targets (bl) of a function, from its instructions."""
    out = []
    for _, t in f["insns"]:
        m = re.match(r"^bl 0x([0-9a-f]{8})$", t)
        if m:
            out.append(int(m.group(1), 16))
    return out


def main():
    mw, cb = load(sys.argv[1]), load(sys.argv[2])
    targets = [int(a, 16) for a in sys.argv[3:]]
    by_key = collections.defaultdict(list)
    by_len = collections.defaultdict(list)
    for a, f in cb.items():
        by_key[key(f)].append(a)
        by_len[len(f["insns"])].append(a)
    callers = collections.defaultdict(set)
    for a, f in mw.items():
        for c in call_sites(f):
            callers[c].add(a)
    norm_cache = {}

    def nseq(funcs, a):
        k = (id(funcs), a)
        if k not in norm_cache:
            norm_cache[k] = [RE_NUM.sub("#", t) for _, t in funcs[a]["insns"]]
        return norm_cache[k]

    def match_caller(a):
        f = mw[a]
        exact = by_key.get(key(f), [])
        if len(exact) == 1:
            return exact[0], 1.0
        s = nseq(mw, a)
        n = len(s)
        best = (0.0, None)
        for ln in range(int(n * 0.85), int(n * 1.15) + 2):
            for c in by_len.get(ln, []):
                sm = difflib.SequenceMatcher(None, s, nseq(cb, c), autojunk=False)
                if sm.real_quick_ratio() <= best[0] or sm.quick_ratio() <= best[0]:
                    continue
                r = sm.ratio()
                if r > best[0]:
                    best = (r, c)
        return best[1], best[0]

    for t in targets:
        votes = collections.Counter()
        detail = []
        for caller in sorted(callers.get(t, ()))[:40]:
            c, r = match_caller(caller)
            if c is None or r < 0.8:
                continue
            ms, cs = call_sites(mw[caller]), call_sites(cb[c])
            if len(ms) != len(cs):
                # Align call lists by the callees already known to be equal
                # in number; fall back to same index when lengths match.
                sm = difflib.SequenceMatcher(None, [0] * len(ms), [0] * len(cs))
            for i, m_target in enumerate(ms):
                if m_target == t and i < len(cs):
                    votes[cs[i]] += 1
                    detail.append((f"{caller:08X}", f"{c:08X}", round(r, 2), f"{cs[i]:08X}"))
        top = votes.most_common(3)
        print(f"MW {t:08X}: {[(f'{a:08X}', n) for a, n in top]}  ({len(callers.get(t, ()))} MW callers)")
        for d in detail[:6]:
            print("    ", d)


if __name__ == "__main__":
    main()
