"""mavpa grid: tempo, meter and downbeat, with the evidence printed.

1. Tempo: librosa's estimate, then a rigid-grid fit (BPM to 0.001, phase to 0.5 ms) that
   maximises onset strength on the beats. Producer tempos are usually whole numbers, so a
   whole (or .5) BPM that fits as well wins.
2. Transient alignment: onset-strength peaks come ~10-30 ms after a hit really starts, and a
   DAW grid line sits at the start. The phase is shifted by the median transient residual.
3. Meter: for 2, 3 and 4 beats per bar, fold harmonic change + bass change + kick onsets by
   beat phase. The true meter gives one strong phase (the downbeat); repetition of chroma at
   4- and 8-bar lags backs it up. Waltzes (3/4) are common in pop and easy to miss.
"""
import numpy as np

from .audio import load_mono
from .grid import Grid

SR = 22050


def _onset_env(y, hop):
    import librosa
    _, yp = librosa.effects.hpss(y)
    o = librosa.onset.onset_strength(y=yp, sr=SR, hop_length=hop)
    return o / (o.max() + 1e-9)


def _scores(oenv, fr, bpm, phases, t1):
    per = 60.0 / bpm
    n = max(4, int((t1 - phases.max()) / per))
    ts = phases[:, None] + per * np.arange(n)[None, :]
    idx = np.clip(np.round(ts * fr).astype(int), 1, len(oenv) - 2)
    v = np.maximum(np.maximum(oenv[idx - 1], oenv[idx]), oenv[idx + 1])
    return v.mean(axis=1)


def fit_bpm(oenv, fr, bpm0, t1, span=0.02):
    best = (-1.0, bpm0, 0.0)
    for bpm in np.arange(bpm0 * (1 - span), bpm0 * (1 + span), 0.01):
        ph = np.arange(0, 60.0 / bpm, 0.004)
        sc = _scores(oenv, fr, bpm, ph, t1)
        i = int(np.argmax(sc))
        if sc[i] > best[0]:
            best = (float(sc[i]), float(bpm), float(ph[i]))
    s, bpm, ph = best
    for b in np.arange(bpm - 0.02, bpm + 0.02, 0.001):
        phs = np.arange(ph - 0.012, ph + 0.012, 0.0005)
        sc = _scores(oenv, fr, b, phs, t1)
        i = int(np.argmax(sc))
        if sc[i] > s:
            s, bpm, ph = float(sc[i]), float(b), float(phs[i])
    return bpm, ph, s


def best_phase(oenv, fr, bpm, t1, around=None):
    if around is None:
        ph = np.arange(0, 60.0 / bpm, 0.0005)
    else:
        ph = np.arange(around - 0.015, around + 0.015, 0.0005)
    sc = _scores(oenv, fr, bpm, ph, t1)
    i = int(np.argmax(sc))
    return float(ph[i]), float(sc[i])


def transient_residuals(y44, sr, grid_t0, step, t_max=None):
    """Start times of drum transients vs a 16th grid starting at grid_t0. Returns residuals in ms."""
    import librosa
    if t_max:
        y44 = y44[: int(t_max * sr)]
    hop = 44
    env = librosa.feature.rms(y=y44, frame_length=256, hop_length=hop, center=False)[0]
    t_env = (np.arange(len(env)) * hop + 128) / sr
    oenv = librosa.onset.onset_strength(y=y44, sr=sr, hop_length=hop, n_fft=512, center=False)
    pk = librosa.util.peak_pick(oenv, pre_max=30, post_max=30, pre_avg=100, post_avg=100,
                                delta=np.percentile(oenv, 99) * 0.3, wait=60)
    starts = []
    for p in pk:
        a = max(0, p - 40)
        seg = env[a:p + 20]
        if len(seg) < 5 or p < 70:
            continue
        pkk = a + int(np.argmax(seg))
        base = env[max(0, p - 60):p - 10].min()
        thr = base + 0.2 * (env[pkk] - base)
        j = pkk
        while j > a and env[j] > thr:
            j -= 1
        starts.append(t_env[j])
    res = (np.array(starts) - grid_t0) / step
    return (res - np.round(res)) * step * 1000.0


def beat_features(ws, grid_bpm, phase, dur):
    """Per-beat chroma (harmony), bass chroma and kick onset, using stems when available."""
    import librosa
    beat = 60.0 / grid_bpm
    have = ws.has_stems()
    harm = load_mono(ws.stem("other"), SR) if have else librosa.effects.harmonic(load_mono(ws.source, SR))
    bass = load_mono(ws.stem("bass"), SR) if have else None
    drums = load_mono(ws.stem("drums"), SR) if have else load_mono(ws.source, SR)
    hop = 256
    C = librosa.feature.chroma_cqt(y=harm, sr=SR, hop_length=hop)
    tc = librosa.times_like(C, sr=SR, hop_length=hop)
    if bass is not None:
        Cb = librosa.feature.chroma_cqt(y=bass, sr=SR, hop_length=hop, fmin=librosa.note_to_hz("C1"), n_octaves=4)
    else:
        Cb = librosa.feature.chroma_cqt(y=harm, sr=SR, hop_length=hop, fmin=librosa.note_to_hz("C1"), n_octaves=2)
    S = np.abs(librosa.stft(drums, n_fft=2048, hop_length=hop))
    f = librosa.fft_frequencies(sr=SR, n_fft=2048)
    low = S[(f >= 30) & (f < 150)].sum(axis=0)
    kick = np.maximum(0, np.diff(low, prepend=low[0]))
    n0 = int(np.floor(-phase / beat)) + 1
    nb = int((dur - phase) / beat) - 1
    B, Bb, K = [], [], []
    for n in range(max(0, n0), nb):
        a, z = phase + n * beat, phase + (n + 1) * beat
        m = (tc >= a) & (tc < z)
        if m.sum() < 2:
            continue
        v = C[:, m].mean(axis=1)
        vb = Cb[:, m].mean(axis=1)
        i = np.searchsorted(tc, a)
        k = kick[max(0, i - 3):i + 4].max()
        B.append(v / (np.linalg.norm(v) + 1e-9))
        Bb.append(vb / (np.linalg.norm(vb) + 1e-9))
        K.append(k)
    return np.array(B), np.array(Bb), np.array(K), max(0, n0)


def _z(x):
    x = np.asarray(x, float)
    return (x - x.mean()) / (x.std() + 1e-9)


def meter_evidence(B, Bb, K, candidates=(2, 3, 4)):
    nov = np.r_[0, 1 - np.sum(B[1:] * B[:-1], axis=1)]
    bnov = np.r_[0, 1 - np.sum(Bb[1:] * Bb[:-1], axis=1)]
    comb = _z(nov) + _z(bnov) + 0.7 * _z(K)
    out = {}
    for G in candidates:
        ph = np.array([comb[np.arange(len(comb)) % G == p].mean() for p in range(G)])
        best = int(np.argmax(ph))
        others = np.delete(ph, best)
        contrast = float(ph[best] - others.mean())
        reps = []
        for bars in (4, 8):
            L = G * bars
            if L < len(B):
                reps.append(float(np.mean(np.sum(B[L:] * B[:-L], axis=1))))
        out[G] = {"phase_scores": ph.round(3).tolist(), "best_phase": best, "contrast": round(contrast, 3),
                  "repeat_4_8_bars": round(float(np.mean(reps)) if reps else 0.0, 4)}
    rep_mean = np.mean([v["repeat_4_8_bars"] for v in out.values()])
    for G, v in out.items():
        v["score"] = round(v["contrast"] + 8.0 * (v["repeat_4_8_bars"] - rep_mean), 3)
    return out


def estimate_grid(ws, bpm=None, meter=None, downbeat=None, lo=70, hi=180, write=False):
    import librosa
    y = load_mono(ws.source, SR)
    dur = len(y) / SR
    hop = 64
    fr = SR / hop
    oenv = _onset_env(y, hop)
    t1 = dur - 0.5

    # ---- tempo
    if bpm:
        bpm_fit = float(bpm)
        ph, sc = best_phase(oenv, fr, bpm_fit, t1)
        note = "forced"
    else:
        t0 = float(np.atleast_1d(librosa.feature.tempo(onset_envelope=librosa.onset.onset_strength(y=y, sr=SR), sr=SR))[0])
        while t0 < lo:
            t0 *= 2
        while t0 > hi:
            t0 /= 2
        bpm_fit, ph, sc = fit_bpm(oenv, fr, t0, t1)
        note = f"librosa {t0:.1f} → fit {bpm_fit:.3f}"
        # producer tempos are whole numbers (sometimes .5): snap when it fits as well
        for cand in sorted({round(bpm_fit), round(bpm_fit * 2) / 2}, key=lambda c: abs(c - bpm_fit)):
            if abs(cand - bpm_fit) > 0.15:
                continue
            pc, scc = best_phase(oenv, fr, cand, t1, around=ph)
            if scc >= 0.995 * sc:
                note += f" → snapped to {cand:g} (fit {scc:.4f} vs {sc:.4f})"
                bpm_fit, ph, sc = float(cand), pc, scc
                break
    beat = 60.0 / bpm_fit
    octaves = {}
    for mult in (0.5, 1.0, 2.0, 1.5, 2 / 3):
        b = bpm_fit * mult
        if lo / 1.5 <= b <= hi * 1.5:
            octaves[round(b, 2)] = round(best_phase(oenv, fr, b, t1)[1], 4)

    # ---- transient alignment (use the drum stem if we have it)
    import soundfile as sf
    src = ws.stem("drums") if ws.has_stems() else ws.source
    y44, sr44 = sf.read(str(src), always_2d=True)
    y44 = y44.mean(axis=1)
    res = transient_residuals(y44, sr44, ph, beat / 4)
    shift = float(np.median(res)) / 1000.0 if len(res) > 20 else 0.0
    ph_aligned = ph + shift
    res2 = transient_residuals(y44, sr44, ph_aligned, beat / 4)

    # ---- meter + downbeat
    B, Bb, K, n0 = beat_features(ws, bpm_fit, ph_aligned, dur)
    ev = meter_evidence(B, Bb, K)
    G = meter or max(ev, key=lambda g: (ev[g]["score"], g == 4))
    if downbeat is not None:
        down = float(downbeat)
    else:
        bp = ev[G]["best_phase"] if G in ev else 0
        first = ph_aligned + (n0 + bp) * beat   # feature row i is beat n0 + i; downbeats are rows i ≡ bp (mod G)
        bar = G * beat
        down = first % bar
        if down > bar - 0.03:
            down -= bar
    g = Grid(bpm=round(bpm_fit, 4), beats_per_bar=int(G), downbeat=round(down, 4))

    # ---- report
    print(f"tempo     {g.bpm:g} BPM   ({note}; grid score {sc:.4f})")
    print("          octave check (higher = more onsets on the grid): "
          + "  ".join(f"{k:g}:{v:.3f}" for k, v in sorted(octaves.items())))
    print(f"phase     onset fit {ph:.4f}s, transient shift {shift * 1000:+.1f} ms over {len(res)} hits "
          f"→ residual median {np.median(res2):+.1f} ms, IQR {np.percentile(res2, 25):+.1f}..{np.percentile(res2, 75):+.1f} ms")
    print("meter     beats/bar: contrast (downbeat stands out) · repetition at 4/8 bars · score")
    for k in sorted(ev):
        v = ev[k]
        mark = "  ←" if k == G else ""
        print(f"            {k}: {v['contrast']:+.3f} · {v['repeat_4_8_bars']:.4f} · {v['score']:+.3f}   phases {v['phase_scores']}{mark}")
    print(f"downbeat  song bar 1 starts at {g.downbeat:.4f}s (bar = {g.bar:.4f}s, {g.beats_per_bar}/4)."
          + (f" Anything before it (a pickup) lands in DAW bar 1." if g.downbeat > 0.05 else ""))
    print(f"length    {g.n_bars(dur)} song bars, {dur:.1f}s")
    if meter is None and len(ev) > 1:
        top = sorted(ev.values(), key=lambda v: -v["score"])
        if top[0]["score"] - top[1]["score"] < 0.3:
            print("WARNING   meter is close: check a structure view and count along before trusting it.")
    result = {"grid": g.to_dict(), "bpm_note": note, "octaves": octaves, "meter_evidence": ev,
              "transient_residual_ms": {"median": float(np.median(res2)), "iqr": [float(np.percentile(res2, 25)), float(np.percentile(res2, 75))],
                                        "n": int(len(res2))}, "duration": dur}
    ws.save("grid.json", result)
    if write:
        spec = ws.spec()
        spec["grid"] = {**spec.get("grid", {}), **g.to_dict()}
        ws.save_spec(spec)
        print("wrote grid to song.json")
    return g, result
