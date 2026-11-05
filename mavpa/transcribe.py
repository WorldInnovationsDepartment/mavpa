"""Draft notes per stem, quantised to the 16th grid, plus loop consensus.

    bass    pYIN pitch per 16th step + low-band re-attacks          (monophonic, very reliable)
    music   basic-pitch (ONNX) on the 'other' stem, or a CQT fallback (polyphonic, a draft)
    vocals  harmonic-sum salience (robust to reverb/doubles) per 16th (monophonic contour)

Loop consensus: a note is kept for loop bar k / step s / pitch p when it shows up there in
at least `min_frac` of the loop's repeats. Repetition kills transcription noise; this is how
the hand-made kits get to ~99% on bass.
"""
import json
from collections import defaultdict

import numpy as np

from .audio import load_mono
from .notes import name as note_name
from .spec import pattern_pos

SR = 22050


def _q(grid, t):
    return (t - grid.downbeat) / grid.step


def _note(grid, q0, ln, pitch, vel):
    spb = grid.steps_per_bar
    return {"bar": int(q0 // spb) + 1, "step": int(q0 % spb), "len": int(max(1, ln)), "pitch": int(pitch), "vel": int(vel)}


def bass_track(ws, grid):
    """Per global 16th step: pitch (MIDI float or nan) and re-attack strength (0..1)."""
    import librosa
    y = load_mono(ws.stem("bass"), SR)
    hop = 256
    f0, vf, _ = librosa.pyin(y, fmin=30, fmax=400, sr=SR, frame_length=4096, hop_length=hop)
    t = librosa.times_like(f0, sr=SR, hop_length=hop)
    m = librosa.hz_to_midi(f0)
    on = librosa.onset.onset_strength(y=y, sr=SR, hop_length=hop, fmax=400, n_mels=64)
    on = on / (np.percentile(on, 99.5) + 1e-9)
    nq = int(_q(grid, len(y) / SR))
    pitch, onset = np.full(nq, np.nan), np.zeros(nq)
    for q in range(nq):
        a, z = grid.downbeat + q * grid.step, grid.downbeat + (q + 1) * grid.step
        sel = (t >= a + 0.004) & (t < z - 0.004)
        v = sel & vf & np.isfinite(m)
        if sel.sum() and v.sum() >= max(2, 0.5 * sel.sum()):
            pitch[q] = float(np.median(m[v]))
        i = np.searchsorted(t, a)
        onset[q] = float(on[max(0, i - 2):i + 3].max())
    return pitch, np.clip(onset, 0, 1)


def notes_from_track(pitch, onset, grid, q_offset=0, onset_thr=0.75, vel=100):
    """Merge a per-step pitch track into notes: equal neighbours join, strong re-attacks split,
    and one-step glide blips (within 2 semitones of the next held note) are absorbed."""
    p = np.array([np.nan if (x is None or not np.isfinite(x)) else round(x) for x in pitch], float)
    runs = []
    for q, x in enumerate(p):
        if np.isnan(x):
            continue
        reattack = onset[q] >= onset_thr and onset[q] >= onset[max(0, q - 1)] and onset[q] >= onset[min(len(onset) - 1, q + 1)]
        if runs and runs[-1][2] == x and runs[-1][0] + runs[-1][1] == q and not reattack:
            runs[-1][1] += 1
        else:
            runs.append([q, 1, x])
    i = 0
    while i < len(runs) - 1:                       # glide blip -> part of the next note
        q, ln, x = runs[i]
        nq, nln, nx = runs[i + 1]
        if ln == 1 and nln >= 2 and q + 1 == nq and abs(nx - x) <= 2:
            runs[i + 1] = [q, nln + 1, nx]
            runs.pop(i)
            continue
        i += 1
    return [_note(grid, q + q_offset, ln, x, vel) for q, ln, x in runs]


def bass_notes(ws, grid):
    pitch, onset = bass_track(ws, grid)
    ws.save("track_bass.json", {"grid": grid.to_dict(), "pitch": [None if not np.isfinite(x) else round(float(x), 2) for x in pitch],
                                "onset": onset.round(3).tolist()})
    return notes_from_track(pitch, onset, grid)


def music_notes(ws, grid, engine="auto", stem="other"):
    if engine in ("auto", "basic-pitch"):
        try:
            import logging
            logging.getLogger().setLevel(logging.ERROR)
            from basic_pitch import ICASSP_2022_MODEL_PATH
            from basic_pitch.inference import predict
            _, _, events = predict(str(ws.stem(stem)), ICASSP_2022_MODEL_PATH, onset_threshold=0.5, frame_threshold=0.3,
                                   minimum_note_length=80, minimum_frequency=40, maximum_frequency=4200,
                                   multiple_pitch_bends=False, melodia_trick=True, midi_tempo=grid.bpm)
            out = []
            for st, en, p, amp, _ in events:
                q0 = int(round(_q(grid, st)))
                q1 = int(round(_q(grid, en)))
                if q0 < 0:
                    continue
                out.append(_note(grid, q0, max(1, q1 - q0), p, np.clip(40 + amp * 90, 30, 127)))
            return out, "basic-pitch"
        except ImportError:
            if engine == "basic-pitch":
                raise SystemExit("basic-pitch is not installed (bin/mavpa installs it; or: pip install --no-deps basic-pitch)")
    return cqt_notes(ws, grid, stem), "cqt"


def cqt_notes(ws, grid, stem="other", lo=36, hi=96):
    """Fallback polyphonic draft: per 16th, semitone CQT peaks that stand out; held while they stay."""
    import librosa
    y = load_mono(ws.stem(stem), SR)
    hop = 256
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=hop, fmin=librosa.midi_to_hz(lo), n_bins=(hi - lo), bins_per_octave=12))
    D = librosa.amplitude_to_db(C, ref=np.max)
    t = librosa.times_like(C, sr=SR, hop_length=hop)
    nq = int(_q(grid, len(y) / SR))
    act = np.zeros((hi - lo, nq), bool)
    for q in range(nq):
        a, z = grid.downbeat + q * grid.step, grid.downbeat + (q + 1) * grid.step
        sel = (t >= a) & (t < z)
        if not sel.any():
            continue
        v = D[:, sel].mean(axis=1)
        peaks = (v > np.r_[v[1:], -200]) & (v > np.r_[-200, v[:-1]]) & (v > v.max() - 18) & (v > -45)
        act[:, q] = peaks
    out = []
    for i in range(hi - lo):
        q = 0
        while q < nq:
            if act[i, q]:
                z = q
                while z + 1 < nq and act[i, z + 1]:
                    z += 1
                if z - q + 1 >= 2:
                    out.append(_note(grid, q, z - q + 1, lo + i, 80))
                q = z + 1
            else:
                q += 1
    return sorted(out, key=lambda n: (n["bar"], n["step"], n["pitch"]))


def vocal_notes(ws, grid, lo="E2", hi="C6"):
    import librosa
    from scipy.ndimage import median_filter
    y = load_mono(ws.stem("vocals"), SR)
    lo_m, hi_m = int(librosa.note_to_midi(lo)), int(librosa.note_to_midi(hi))
    hop = 256
    fmin_m = lo_m - 1
    nb = (hi_m + 36 - fmin_m) * 3
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=hop, fmin=librosa.midi_to_hz(fmin_m), n_bins=nb, bins_per_octave=36))
    C = C / (C.max() + 1e-9)
    t = librosa.times_like(C, sr=SR, hop_length=hop)
    cands = np.arange(lo_m, hi_m + 1)
    sal = np.zeros((len(cands), C.shape[1]))
    for ci, m in enumerate(cands):
        for h, w in zip((1, 2, 3, 4, 5), (1.0, 0.8, 0.6, 0.45, 0.35)):
            b = int(round((m + 12 * np.log2(h) - fmin_m) * 3))
            if b < C.shape[0]:
                sal[ci] += w * C[max(0, b - 1):b + 2].max(axis=0)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    rdb = 20 * np.log10(rms + 1e-9)
    voiced = (rdb > np.percentile(rdb, 98) - 28) & (sal.max(axis=0) / (sal.mean(axis=0) + 1e-9) > 2.0)
    best = cands[np.argmax(sal, axis=0)].astype(float)
    best[~voiced] = np.nan
    med = median_filter(np.nan_to_num(best, nan=0.0), size=15)
    for i in range(len(best)):                       # octave-jump repair against the running median
        if np.isfinite(best[i]) and med[i] > 0:
            while best[i] - med[i] > 9:
                best[i] -= 12
            while med[i] - best[i] > 9:
                best[i] += 12
    nq = int(_q(grid, t[-1]))
    notes, cur = [], None
    for q in range(nq):
        a, z = grid.downbeat + q * grid.step, grid.downbeat + (q + 1) * grid.step
        m = (t >= a) & (t < z)
        v = best[m]
        v = v[np.isfinite(v)]
        p = None
        if len(v) >= max(2, 0.5 * m.sum()):
            vals, cnt = np.unique(v, return_counts=True)
            p = int(vals[np.argmax(cnt)])
        if p is None:
            if cur:
                notes.append(cur)
                cur = None
            continue
        if cur and cur["pitch"] == p:
            cur["len"] += 1
            continue
        if cur:
            notes.append(cur)
        cur = {"q": q, "len": 1, "pitch": p}
    if cur:
        notes.append(cur)
    return [_note(grid, n["q"], n["len"], n["pitch"], 90) for n in notes]


def consensus(notes, grid, segments, P, min_frac=0.5, active_bars=None):
    """segments: [(from_bar, to_bar, anchor)] -> ({pos: [[step, len, name, vel]]}, n_repeats)."""
    hits = defaultdict(list)
    reps = set()
    for si, (a, z, anc) in enumerate(segments):
        for bar in range(a, z + 1):
            cyc = (bar - anc) // P
            first = anc + cyc * P
            if first >= a and first + P - 1 <= z and (active_bars is None or all(b in active_bars for b in range(first, first + P))):
                reps.add((si, cyc))
    for n in notes:
        for si, (a, z, anc) in enumerate(segments):
            if a <= n["bar"] <= z:
                cyc = (n["bar"] - anc) // P
                if (si, cyc) in reps:
                    hits[(pattern_pos(n["bar"], anc, P), n["step"], n["pitch"])].append((si, cyc, n["len"], n["vel"]))
                break
    nrep = max(1, len(reps))
    pat = defaultdict(list)
    for (k, s, p), lst in hits.items():
        rs = {(x[0], x[1]) for x in lst}
        if len(rs) / nrep >= min_frac:
            pat[str(k)].append([int(s), int(np.median([x[2] for x in lst])), note_name(p), int(np.median([x[3] for x in lst])), round(len(rs) / nrep, 2)])
    for k in pat:
        pat[k].sort(key=lambda x: (x[0], -_pitch(x[2])))
    return {k: [x[:4] for x in v] for k, v in sorted(pat.items(), key=lambda kv: int(kv[0]))}, nrep, {k: [x[4] for x in v] for k, v in pat.items()}


def consensus_mono(ws, grid, segments, P, min_frac=0.5):
    """Loop consensus for a monophonic part from its per-step track (work/track_bass.json)."""
    d = ws.load("track_bass.json")
    pitch = np.array([np.nan if x is None else x for x in d["pitch"]], float)
    onset = np.array(d["onset"], float)
    spb = grid.steps_per_bar
    votes = [[[] for _ in range(spb)] for _ in range(P)]
    ons = np.zeros((P, spb))
    n = 0
    for a, z, anc in segments:
        b = a + ((anc - a) % P)
        while b + P - 1 <= z:
            for k in range(P):
                for s_ in range(spb):
                    q = (b + k - 1) * spb + s_
                    if q < len(pitch):
                        votes[k][s_].append(pitch[q])
                        ons[k, s_] += onset[q]
            n += 1
            b += P
    n = max(1, n)
    track, share = np.full(P * spb, np.nan), np.zeros(P * spb)
    for k in range(P):
        for s_ in range(spb):
            v = np.array([round(x) for x in votes[k][s_] if np.isfinite(x)])
            if len(v):
                vals, cnt = np.unique(v, return_counts=True)
                j = int(np.argmax(cnt))
                if cnt[j] / n >= min_frac:
                    track[k * spb + s_] = vals[j]
                    share[k * spb + s_] = cnt[j] / n
    notes = notes_from_track(track, (ons / n).ravel(), grid, onset_thr=0.9)
    pat, fr = {}, {}
    for nt in notes:
        k = str(nt["bar"])
        pat.setdefault(k, []).append([nt["step"], nt["len"], note_name(nt["pitch"]), nt["vel"]])
        q = (nt["bar"] - 1) * spb + nt["step"]
        fr.setdefault(k, []).append(round(float(share[q:q + nt["len"]].mean()), 2))
    return pat, n, fr


def _pitch(name):
    from .notes import num
    return num(name)


def write_notes_midi(path, notes, grid, program=0, is_drum=False):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=grid.bpm, resolution=960)
    pm.time_signature_changes.append(pretty_midi.TimeSignature(grid.beats_per_bar, grid.beat_unit, 0))
    ins = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for n in notes:
        t0 = grid.daw_t(n["bar"], n["step"])
        ins.notes.append(pretty_midi.Note(velocity=int(n["vel"]), pitch=int(n["pitch"]), start=t0, end=t0 + n["len"] * grid.step))
    pm.instruments.append(ins)
    pm.write(str(path))


def get_notes(ws, part, engine="auto", refresh=False):
    """Cached draft notes for a part (work/notes_<part>.json)."""
    grid = ws.grid()
    cache = ws.work / f"notes_{part}.json"
    if cache.exists() and not refresh:
        d = json.loads(cache.read_text())
        if d.get("grid") == grid.to_dict():
            return d["notes"], d.get("engine", "")
    if part == "bass":
        notes, eng = bass_notes(ws, grid), "pyin"
    elif part in ("vocals", "vocal"):
        notes, eng = vocal_notes(ws, grid), "salience"
    elif part in ("music", "other"):
        notes, eng = music_notes(ws, grid, engine)
    else:
        notes, eng = music_notes(ws, grid, engine, stem=part)
    ws.save(f"notes_{part}.json", {"grid": grid.to_dict(), "engine": eng, "notes": notes})
    write_notes_midi(ws.work / f"notes_{part}.mid", notes, grid)
    return notes, eng


def segments_for(ws, bars=None, period=None, anchor=None):
    a = ws.load("analysis.json") or {}
    P = period or a.get("loop", {}).get("period") or 4
    if bars:
        return [(bars[0], bars[1], anchor or bars[0])], P
    segs = [(s["from"], s["to"], s["anchor"]) for s in a.get("loop", {}).get("segments", [])]
    if not segs:
        raise SystemExit("no loop segments: run `mavpa analyze` first or pass --bars A-B --period P")
    return segs, P


def transcribe_cmd(ws, part, bars=None, period=None, anchor=None, min_frac=0.5, engine="auto"):
    grid = ws.grid()
    notes, eng = get_notes(ws, part, engine, refresh=True)
    print(f"{part}: {len(notes)} draft notes ({eng}) → work/notes_{part}.json + .mid (aligned like the kit: drop at bar 1)")
    segs, P = segments_for(ws, bars, period, anchor)
    if part == "bass":
        pat, nrep, fr = consensus_mono(ws, grid, segs, P, min_frac)
    else:
        pat, nrep, fr = consensus(notes, grid, segs, P, min_frac)
    sn = grid.step_names()
    print(f"loop consensus over {nrep} repeats of {P} bars (segments {segs}), keeping notes in ≥{min_frac:.0%} of repeats:")
    print("  format: step:note(len16)[share of repeats]")
    for k in range(1, P + 1):
        row = pat.get(str(k), [])
        print(f"  loop bar {k}: " + "  ".join(f"{sn[s % len(sn)]}:{n}({ln})[{f:.0%}]" for (s, ln, n, v), f in zip(row, fr.get(str(k), []))))
    ws.save(f"consensus_{part}.json", {"period": P, "segments": segs, "min_frac": min_frac, "repeats": nrep, "pattern": pat})
    return pat
