"""Drum hits from the drum stem, per frequency band, on the 16th grid.

Bands (edit with care): kick 30-150 Hz, snare/clap/rim 180-5000 Hz, hats/shakers 7-16 kHz.
Each 16th step gets an onset strength per band; hits are steps that stand out from that
band's typical level. Folding over the loop gives "how often is there a hit here" grids,
the same evidence a producer would use by looping a bar and listening.
Optional NMF (--components K) learns K drum sounds from the spectrogram instead of fixed bands.
"""
import numpy as np

BANDS = {"kick": (30, 150), "snare": (180, 5000), "hat": (7000, 16000)}
GM = {"kick": 36, "snare": 38, "hat": 42, "perc": 39}


def band_steps(ws, grid, bands=BANDS):
    """-> {band: array of strengths per global 16th step (0..1)}, n_steps"""
    import librosa
    import soundfile as sf
    y, sr = sf.read(str(ws.stem("drums")), always_2d=True)
    y = y.mean(axis=1)
    hop, nfft = 256, 2048
    S = np.abs(librosa.stft(y, n_fft=nfft, hop_length=hop)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=nfft)
    t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=hop)
    nq = int((len(y) / sr - grid.downbeat) / grid.step)
    out = {}
    for name, (lo, hi) in bands.items():
        band = S[(f >= lo) & (f < hi)].sum(axis=0)
        e = np.log1p(band / (10 ** -2.5 * np.percentile(band, 99) + 1e-12))   # floor 25 dB under the band's loud hits
        flux = np.maximum(0, np.diff(e, prepend=e[0]))
        v = np.zeros(nq)
        for q in range(nq):
            tq = grid.downbeat + q * grid.step
            sel = (t >= tq - 0.3 * grid.step) & (t < tq + 0.4 * grid.step)
            v[q] = flux[sel].max() if sel.any() else 0.0
        out[name] = v / (np.percentile(v, 99.5) + 1e-9)
    return out, nq


def fold_mean(v, grid, segments, P):
    """Mean strength per (loop bar, step) over all full repeats -> (P x steps) array, repeats."""
    spb = grid.steps_per_bar
    acc, n = np.zeros((P, spb)), 0
    for a, z, anc in segments:
        b = a + ((anc - a) % P)
        while b + P - 1 <= z:
            q0 = (b - 1) * spb
            block = v[q0:q0 + P * spb]
            if len(block) == P * spb:
                acc += block.reshape(P, spb)
                n += 1
            b += P
    return acc / max(1, n), n


def otsu(x):
    x = np.sort(np.asarray(x).ravel())
    best, thr = -1, x[-1]
    for i in range(1, len(x)):
        w0, w1 = i / len(x), 1 - i / len(x)
        var = w0 * w1 * (x[:i].mean() - x[i:].mean()) ** 2
        if var > best:
            best, thr = var, (x[i - 1] + x[i]) / 2
    return float(thr)


def grid_from_mean(M, floor=0.1):
    """Steps that clearly stand out (Otsu split of the folded means) become hits; X/x/g by strength."""
    thr = max(otsu(M), floor)
    top = M.max() + 1e-9
    out = {}
    for k in range(M.shape[0]):
        out[str(k + 1)] = "".join("." if m < thr else ("X" if m >= 0.7 * top else ("x" if m >= 0.42 * top else "g")) for m in M[k])
    return out, thr


def draft_drums(ws, grid, segments, P):
    strengths, nq = band_steps(ws, grid)
    if "kick" in strengths:                            # a kick's own tail is not a second kick on the next 16th
        k = strengths["kick"]
        tail = np.r_[False, k[1:] < 0.6 * k[:-1]]
        strengths["kick"] = np.where(tail, 0.0, k)
    if "kick" in strengths and "snare" in strengths:   # kick clicks leak into the snare band
        strengths["snare"] = np.clip(strengths["snare"] - 0.6 * strengths["kick"], 0, None)
    pats, info = {}, {}
    for band, v in strengths.items():
        M, n = fold_mean(np.clip(v, 0, 1), grid, segments, P)
        pats[band], thr = grid_from_mean(M)
        info[band] = {"threshold": round(thr, 3), "repeats": n, "mean": M.round(3).tolist()}
    return pats, info, strengths


def drums_cmd(ws, bars=None, period=None, anchor=None, components=0):
    from .transcribe import segments_for
    grid = ws.grid()
    segs, P = segments_for(ws, bars, period, anchor)
    pats, info, _ = draft_drums(ws, grid, segs, P)
    sn = grid.step_names()
    print(f"drums folded over {P}-bar loop, segments {segs}")
    print("digits = mean onset strength at that step over all repeats (0-9, relative to the band's strongest step);")
    print("the draft grid keeps steps above an automatic split between 'hit' and 'nothing'")
    for band in pats:
        M = np.array(info[band]["mean"])
        top = M.max() + 1e-9
        print(f"\n### {band} {BANDS[band][0]}-{BANDS[band][1]} Hz  (split at {info[band]['threshold']}, {info[band]['repeats']} repeats)")
        print("            " + " ".join(f"{s:>2}" for s in sn))
        for k in range(P):
            print(f"  bar {k + 1:2d}:   " + " ".join(f"{int(round(9 * x / top)):>2}" for x in M[k]) + f"    {pats[band][str(k + 1)]}")
    if components:
        nmf_view(ws, grid, segs, P, components)
    ws.save("drums_draft.json", {"period": P, "segments": segs, "grid": pats, "info": info})
    return pats


def fold(marks, grid, segments, P):
    """Share of repeats with a hit per (loop bar, step) for a string of marks."""
    v = (np.asarray(marks) != ".").astype(float)
    M, n = fold_mean(v, grid, segments, P)
    return M, None, n


def nmf_view(ws, grid, segs, P, k):
    """Learn k drum sounds with NMF and fold each one's hits over the loop (prints like above)."""
    import librosa
    import soundfile as sf
    from sklearn.decomposition import NMF
    y, sr = sf.read(str(ws.stem("drums")), always_2d=True)
    y = y.mean(axis=1)
    hop, nfft = 256, 2048
    S = np.abs(librosa.stft(y, n_fft=nfft, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=nfft)
    edges = 30.0 * 2 ** (np.arange(0, np.log2(18000 / 30.0), 1 / 6))
    B = np.array([S[(f >= edges[i]) & (f < edges[i + 1])].sum(axis=0) for i in range(len(edges) - 1)])
    model = NMF(n_components=k, init="nndsvda", max_iter=500, random_state=0, beta_loss="kullback-leibler", solver="mu")
    W = model.fit_transform(B)
    H = model.components_
    centers = np.sqrt(edges[:-1] * edges[1:])
    t = librosa.frames_to_time(np.arange(H.shape[1]), sr=sr, hop_length=hop)
    order = np.argsort([(W[:, c] * centers).sum() / W[:, c].sum() for c in range(k)])
    sn = grid.step_names()
    for rank, c in enumerate(order):
        h = H[c] / (H[c].max() + 1e-9)
        dh = np.maximum(0, np.diff(h, prepend=h[0]))
        pk = librosa.util.peak_pick(dh, pre_max=6, post_max=6, pre_avg=40, post_avg=40, delta=0.08, wait=8)
        marks = np.full(int((len(y) / sr - grid.downbeat) / grid.step) + 1, ".", dtype="<U1")
        for i in pk:
            if h[min(len(h) - 1, i + 2)] > 0.15:
                q = int(round((t[i] - grid.downbeat) / grid.step))
                if 0 <= q < len(marks):
                    marks[q] = "x"
        share, _, n = fold(marks, grid, segs, P)
        cen = (W[:, c] * centers).sum() / W[:, c].sum()
        print(f"\n### NMF component {rank}: spectral centroid {cen:.0f} Hz, peak {centers[np.argmax(W[:, c])]:.0f} Hz ({n} repeats)")
        print("            " + " ".join(f"{s:>2}" for s in sn))
        for kk in range(P):
            print(f"  bar {kk + 1:2d}:   " + " ".join(f"{int(round(9 * x)):>2}" for x in share[kk]))
