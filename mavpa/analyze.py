"""mavpa analyze: what plays where, in which key, over which chords, in which loop.

Writes work/analysis.json and views/structure.png, prints a compact per-bar table.
Everything is per song bar on the grid from song.json.
"""
import numpy as np

from .audio import db, load_mono
from .notes import MODES, PC_NAMES, name as note_name

SR = 22050
HOP = 512
QUAL = {"": [0, 4, 7], "m": [0, 3, 7], "5": [0, 7], "sus2": [0, 2, 7], "sus4": [0, 5, 7], "7": [0, 4, 7, 10],
        "m7": [0, 3, 7, 10], "maj7": [0, 4, 7, 11], "m7b5": [0, 3, 6, 10], "dim": [0, 3, 6], "aug": [0, 4, 8],
        "6": [0, 4, 7, 9], "add9": [0, 2, 4, 7], "madd9": [0, 2, 3, 7]}
PRIOR = {"": 0.0, "m": 0.0, "5": -0.07, "sus2": -0.05, "sus4": -0.05, "7": -0.03, "m7": -0.03, "maj7": -0.04,
         "m7b5": -0.07, "dim": -0.1, "aug": -0.12, "6": -0.06, "add9": -0.06, "madd9": -0.06}
ROMAN = ["I", "♭II", "II", "♭III", "III", "IV", "♯IV", "V", "♭VI", "VI", "♭VII", "VII"]


def _templates():
    out = []
    for r in range(12):
        for q, iv in QUAL.items():
            v = np.zeros(12)
            for k, i in enumerate(iv):
                v[(r + i) % 12] = 1.0 if k in (0, len(iv) - 1 if q == "5" else 2) else 0.9
            out.append((PC_NAMES[r] + q, r, q, v / np.linalg.norm(v)))
    return out


TEMPL = _templates()


def best_chords(chv, bass_pc=None, k=3):
    sc = []
    for nm, r, q, v in TEMPL:
        s = float(chv @ v) + PRIOR[q] + (0.08 if bass_pc is not None and bass_pc == r else 0.0)
        sc.append((s, nm, r, q))
    sc.sort(reverse=True)
    return sc[:k]


def roman(root_pc, quality, tonic_pc):
    rn = ROMAN[(root_pc - tonic_pc) % 12]
    if quality.startswith("m") and not quality.startswith("maj"):
        rn = rn.lower()
    if quality in ("dim", "m7b5"):
        rn = rn.lower() + "°"
    return rn + {"7": "7", "m7": "7", "maj7": "maj7", "sus2": "sus2", "sus4": "sus4", "5": "5", "6": "6"}.get(quality, "")


def detect_key(chroma_total, bass_hist, home_bass=()):
    """Best 7-note diatonic collection, then the tonic inside it.

    Tonic cues: how often a note is the bass, how loud it is overall, whether the loop's
    first bar / the song's first bar sits on it, and how strong its own triad is."""
    c = chroma_total / (chroma_total.sum() + 1e-9)
    fits = []
    for parent in range(12):
        pcs = {(parent + s) % 12 for s in (0, 2, 4, 5, 7, 9, 11)}
        fits.append((float(sum(c[p] for p in pcs)), parent, pcs))
    fits.sort(reverse=True)
    fit, parent, pcs = fits[0]
    b = bass_hist / (bass_hist.sum() + 1e-9)

    def triad(p):
        third = 3 if (p + 3) % 12 in pcs else 4
        return c[p] + c[(p + third) % 12] + c[(p + 7) % 12]

    outside = [p for p in range(12) if p not in pcs]
    lead = max(outside, key=lambda p: c[p])            # e.g. G# in A minor (the raised 7th of a V chord)
    lead_to = (lead + 1) % 12 if c[lead] >= 0.03 else None

    def score(p):
        home = sum(w for hp, w in zip(home_bass, (0.3, 0.15)) if hp == p)
        return 1.0 * b[p] + 0.35 * c[p] + 0.3 * triad(p) + home + (0.15 if p == lead_to else 0.0)
    cand = sorted(pcs, key=lambda p: -score(p))
    tonic = cand[0]
    deg = [(parent + s) % 12 for s in (0, 2, 4, 5, 7, 9, 11)].index(tonic)
    mode = MODES[deg]
    outside = sorted(((c[p], PC_NAMES[p]) for p in range(12) if p not in pcs), reverse=True)
    return {"tonic": PC_NAMES[tonic], "tonic_pc": tonic, "mode": mode, "parent_major": PC_NAMES[parent],
            "scale_fit": round(fit, 3), "name": f"{PC_NAMES[tonic]} {mode.title() if mode not in ('ionian', 'aeolian') else ('major' if mode == 'ionian' else 'minor')}",
            "scale_hint": "white keys only" if parent == 0 else f"the notes of {PC_NAMES[parent]} major",
            "outside_notes": [f"{n} {v:.0%}" for v, n in outside[:3]],
            "alternatives": [f"{PC_NAMES[p]} ({MODES[[(parent + s) % 12 for s in (0, 2, 4, 5, 7, 9, 11)].index(p)]})" for p in cand[1:3]]}


def bar_matrix(ws, grid, nbars):
    """Per-bar features from the stems."""
    import librosa
    have = ws.has_stems()
    stems = ["drums", "bass", "other", "vocals"] if have else ["mix"]
    levels = {}
    for s in stems:
        y = load_mono(ws.stem(s), SR)
        r = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
        t = librosa.times_like(r, sr=SR, hop_length=HOP)
        lv = []
        for b in range(1, nbars + 1):
            m = (t >= grid.t(b)) & (t < grid.t(b + 1))
            lv.append(float(db(np.sqrt(np.mean(r[m] ** 2))) if m.any() else -120.0))
        levels[s] = np.array(lv)
    harm = load_mono(ws.stem("other"), SR) if have else librosa.effects.harmonic(load_mono(ws.source, SR))
    tun = float(librosa.estimate_tuning(y=harm, sr=SR))
    C = librosa.feature.chroma_cqt(y=harm, sr=SR, hop_length=HOP, tuning=tun, bins_per_octave=36, n_octaves=6,
                                   fmin=librosa.note_to_hz("C2"))
    tc = librosa.times_like(C, sr=SR, hop_length=HOP)
    yb = load_mono(ws.stem("bass"), SR) if have else harm
    Cb = librosa.feature.chroma_cqt(y=yb, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_octaves=3)
    return levels, C, Cb, tc, tun


def pyin_bass(ws, grid, nbars):
    """Median MIDI pitch of the bass stem per 8th note (None = silent)."""
    import librosa
    if not ws.has_stems():
        return [[None] * (grid.beats_per_bar * 2) for _ in range(nbars)]
    y = load_mono(ws.stem("bass"), SR)
    f0, vf, _ = librosa.pyin(y, fmin=30, fmax=400, sr=SR, frame_length=4096, hop_length=HOP)
    t = librosa.times_like(f0, sr=SR, hop_length=HOP)
    m = librosa.hz_to_midi(f0)
    out = []
    for b in range(1, nbars + 1):
        row = []
        for e in range(grid.beats_per_bar * 2):
            a, z = grid.t(b, e * 2) + 0.02, grid.t(b, e * 2 + 2) - 0.02
            sel = (t >= a) & (t < z) & vf & np.isfinite(m)
            row.append(round(float(np.median(m[sel])), 2) if sel.sum() >= 2 else None)
        out.append(row)
    return out


def loop_period(F, active, lags=(1, 2, 4, 8, 16)):
    rep = {}
    idx = np.where(active)[0]
    for L in lags:
        pairs = [(i, i + L) for i in idx if i + L < len(F) and active[i + L]]
        if len(pairs) >= 4:
            rep[L] = float(np.mean([F[i] @ F[j] for i, j in pairs]))
    if not rep:
        return 4, rep
    best = max(rep, key=lambda L: rep[L])
    for L in sorted(rep):                      # prefer the shortest period that repeats as well
        if L < best and rep[L] >= rep[best] - 0.004 and best % L == 0:
            return L, rep
    return best, rep


def loop_anchors(F, active, P, ref_start):
    """Which song bar each loop restart lands on. Returns [(from_bar, to_bar, anchor_bar, match)] (1-based)."""
    n = len(F)
    ref = [ref_start + k for k in range(P) if ref_start + k < n]
    if len(ref) < P:
        return []
    S = np.array([[F[b] @ F[r] for r in ref] for b in range(n)])
    M = np.zeros((n, P))
    for o in range(P):
        for b in range(n):
            M[b, o] = S[b, (b - o) % P]
    win = max(2, P)
    Ms = np.array([M[max(0, b - win // 2):b + win // 2 + 1].mean(axis=0) for b in range(n)])
    off = Ms.argmax(axis=1)
    match = Ms.max(axis=1)
    segs = []
    for b in range(n):
        if not active[b]:
            continue
        o = int(off[b])
        if segs and segs[-1][3] == o and segs[-1][1] >= b - 1:
            segs[-1][1] = b
            segs[-1][4].append(match[b])
        else:
            segs.append([b, b, None, o, [match[b]]])
    good = [g for g in segs if g[1] - g[0] + 1 >= max(2, P // 2) and np.mean(g[4]) >= 0.85]
    merged = []
    for g in good:                               # glue segments with the same phase across short gaps
        if merged and (g[3] - merged[-1][3]) % P == 0 and g[0] - merged[-1][1] <= P:
            merged[-1][1] = g[1]
            merged[-1][4] += g[4]
        else:
            merged.append(g)
    out = []
    for a, z, _, o, ms in merged:
        anchor = a + ((o - a) % P)              # first bar >= a whose loop position is 1
        out.append((a + 1, z + 1, anchor + 1, round(float(np.mean(ms)), 3)))
    return out


def sections_from(active_sets, nbars, min_len=2):
    runs = []
    for b in range(nbars):
        sig = active_sets[b]
        if runs and runs[-1][2] == sig:
            runs[-1][1] = b
        else:
            runs.append([b, b, sig])
    marks = []
    merged = []
    for r in runs:
        if merged and r[1] - r[0] + 1 < min_len:
            prev_sig = merged[-1][2]
            lost = sorted(set(prev_sig) - set(r[2]))
            if lost:
                marks.append({"bars": list(range(r[0] + 1, r[1] + 2)), "lost": lost})
            merged[-1][1] = r[1]
            continue
        if merged and merged[-1][2] == r[2]:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    while len(merged) > 1 and not merged[-1][2]:   # silent tail -> part of the previous section
        merged[-2][1] = merged[-1][1]
        merged.pop()
    secs = []
    n_vox = n_brk = n_main = 0
    has_vox = any("vocals" in m[2] for m in merged)
    for i, (a, z, sig) in enumerate(merged):
        if "vocals" in sig:
            n_vox += 1
            nm = f"Vocal {n_vox}"
        elif not has_vox and "drums" in sig and 0 < i < len(merged) - 1 or (not has_vox and "drums" in sig and i == 0 and len(merged) == 1):
            n_main += 1
            nm = f"Main {n_main}"
        elif i == 0:
            nm = "Intro"
        elif i == len(merged) - 1:
            nm = "Outro"
        else:
            n_brk += 1
            nm = f"Break {n_brk}"
        secs.append({"name": nm, "from": a + 1, "to": z + 1, "stems": sorted(sig)})
    return secs, marks


def analyze(ws, period=None, quiet=False):
    grid = ws.grid()
    from .audio import duration
    dur = duration(ws.source)
    nbars = grid.n_bars(dur)
    levels, C, Cb, tc, tun = bar_matrix(ws, grid, nbars)

    # activity: a stem is "in" when it is within 22 dB of its own loud bars
    # a stem is present at all when it is within 30 dB of the loudest stem (else it is separation bleed),
    # and active in a bar when it is near its own loud bars and not buried under the other stems
    active = {}
    loudest = max(np.percentile(lv, 90) for lv in levels.values())
    bar_max = np.max(np.array(list(levels.values())), axis=0)
    for s, lv in levels.items():
        ref = np.percentile(lv, 90)
        present = ref >= loudest - 30
        active[s] = (lv > ref - 22) & (lv > bar_max - 35) & (lv > -70) & present
    music = active.get("other", active.get("mix")) | active.get("bass", False)

    # per-bar chroma (per beat, concatenated) for structure; bar chroma for chords
    F, chords = [], []
    bass8 = pyin_bass(ws, grid, nbars)
    chroma_total = np.zeros(12)
    bass_hist = np.zeros(12)
    for b in range(1, nbars + 1):
        cb = []
        for k in range(grid.beats_per_bar):
            m = (tc >= grid.t(b) + k * grid.beat) & (tc < grid.t(b) + (k + 1) * grid.beat)
            v = C[:, m].mean(axis=1) if m.any() else np.zeros(12)
            vb = Cb[:, m].mean(axis=1) if m.any() else np.zeros(12)
            cb.append(np.r_[v / (np.linalg.norm(v) + 1e-9), 0.6 * vb / (np.linalg.norm(vb) + 1e-9)])
        f = np.concatenate(cb)
        F.append(f / (np.linalg.norm(f) + 1e-9))
        m = (tc >= grid.t(b)) & (tc < grid.t(b + 1))
        chv = C[:, m].mean(axis=1) if m.any() else np.zeros(12)
        if music[b - 1]:
            chroma_total += chv
        notes8 = [x for x in bass8[b - 1] if x is not None]
        bpc = int(np.bincount([int(round(x)) % 12 for x in notes8], minlength=12).argmax()) if notes8 else None
        for x in notes8:
            bass_hist[int(round(x)) % 12] += 1
        chv = chv / (np.linalg.norm(chv) + 1e-9)
        top = best_chords(chv, bpc)
        chords.append({"best": top[0][1], "root": top[0][2], "q": top[0][3], "score": round(top[0][0], 3),
                       "alts": [f"{t[1]} {t[0]:.2f}" for t in top[1:]], "bass_pc": bpc})
    F = np.array(F)

    # loop period + where the loop restarts
    P, rep = (period, {}) if period else loop_period(F, music)
    first_full = next((i for i in range(nbars) if music[i] and all(music[i:i + P])), 0)
    anchors = loop_anchors(F, music, P, first_full)

    def bar_bass(i):
        if "bass" in active and not active["bass"][i]:      # silent bass stem: only bleed, ignore
            return None
        xs = [int(round(x)) % 12 for x in bass8[i] if x is not None]
        return int(np.bincount(xs, minlength=12).argmax()) if xs else None
    first_song = next((i for i in range(nbars) if bar_bass(i) is not None), 0)
    loop_root = bar_bass(first_full) if bar_bass(first_full) is not None else chords[first_full]["root"]
    key = detect_key(chroma_total, bass_hist, home_bass=(loop_root, bar_bass(first_song)))
    for c in chords:
        c["roman"] = roman(c["root"], c["q"], key["tonic_pc"])
        if c["bass_pc"] is not None and c["bass_pc"] != c["root"]:
            c["best"] += f"/{PC_NAMES[c['bass_pc']]}"

    # sections: runs of the same set of active stems
    sets = [tuple(sorted(s for s in active if active[s][b])) for b in range(nbars)]
    secs, marks = sections_from(sets, nbars)
    for s in secs:
        s["t"] = round(grid.t(s["from"]), 2)

    res = {"grid": grid.to_dict(), "bars": nbars, "duration": dur, "tuning_cents": round(tun * 100, 1), "key": key,
           "loop": {"period": P, "repetition_by_lag": {str(k): round(v, 4) for k, v in rep.items()},
                    "reference_bar": first_full + 1, "segments": [{"from": a, "to": z, "anchor": an, "match": mt} for a, z, an, mt in anchors]},
           "sections": secs, "marks": marks,
           "per_bar": [{"bar": b + 1, "t": round(grid.t(b + 1), 3), "levels": {s: round(float(levels[s][b]), 1) for s in levels},
                        "active": [s for s in active if active[s][b]], "bass8": bass8[b], "chord": chords[b]["best"],
                        "roman": chords[b]["roman"], "chord_score": chords[b]["score"], "alts": chords[b]["alts"]}
                       for b in range(nbars)]}
    ws.save("analysis.json", res)
    np.save(ws.work / "bar_features.npy", F)

    # ---- report
    print(f"key       {key['name']}  (scale = {key['scale_hint']}; fit {key['scale_fit']:.0%}; tonic alternatives "
          f"{', '.join(key['alternatives'])}; strongest outside notes {', '.join(key['outside_notes'])})")
    print(f"tuning    {tun * 100:+.1f} cents")
    print(f"loop      period {P} bars  (chroma repetition by lag: "
          + ", ".join(f"{k}:{v:.3f}" for k, v in rep.items()) + ")")
    for sg in res["loop"]["segments"]:
        print(f"          bars {sg['from']:3d}-{sg['to']:3d}: loop bar 1 falls on song bar {sg['anchor']} (+{P}n), match {sg['match']:.2f}")
    print("sections  " + " | ".join(f"{s['name']} {s['from']}-{s['to']} [{','.join(x[0] for x in s['stems'])}]" for s in secs))
    if marks:
        print("marks     " + "; ".join(f"bars {m['bars']}: {'/'.join(m['lost'])} out" for m in marks))
    if not quiet:
        print("\n bar    t(s)   stems  bass (8ths)                      chord        roman")
        for row in res["per_bar"]:
            st = "".join(s[0].upper() if s in row["active"] else "." for s in levels)
            bs = " ".join(f"{note_name(x):>3}" if x is not None else "  ." for x in row["bass8"])
            print(f"{row['bar']:4d} {row['t']:7.2f}   {st:5s}  {bs:32s} {row['chord']:12s} {row['roman']}")
    from .views import structure_png
    path = structure_png(ws, grid, F, levels, secs)
    print(f"\nview: {path}")
    return res
