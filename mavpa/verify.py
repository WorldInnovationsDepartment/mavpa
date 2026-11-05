"""mavpa verify: score the built kit against the separated stems.

    align    drum transients in kit/audio vs the DAW 16th grid (ms)
    bass     8th-note windows where the bass stem's pitch == the MIDI note
    harmony  per-bar pitch-class similarity of the 'other'-stem layers vs the stem's chroma,
             next to a random-transposition baseline (what a wrong answer would score)
    vocal    sung 16ths whose pitch class matches the guide note (and within a whole tone)
    drums    share of written hits with a real onset in that instrument's band (precision)

Results go to work/verify.json; their summary feeds the guide's "How sure is this?" section.
Gates are rules of thumb for a kit that is good enough to learn from, not truth.
"""
import numpy as np

from .audio import load_mono
from .spec import render

SR = 22050
GATES = {"align_ms": 5.0, "bass": 0.85, "harmony_margin": 0.25, "vocal_tone": 0.7, "drums": 0.8}
BAND_OF = {35: "kick", 36: "kick", 37: "snare", 38: "snare", 39: "snare", 40: "snare", 41: "kick", 42: "hat", 44: "hat",
           46: "hat", 49: "hat", 51: "hat", 54: "hat", 56: "snare", 70: "hat", 82: "hat"}


def _kit_stem(ws, stem):
    spec = ws.spec()
    for it in spec.get("audio") or []:
        if it["stem"] == stem:
            p = ws.kit / "audio" / f"{it['name']}.wav"
            if p.exists():
                return p
    return None


def verify(ws):
    from .tempo import transient_residuals
    import librosa
    import soundfile as sf
    spec = ws.spec()
    grid = ws.grid()
    notes = render(spec)
    layers = {ly["id"]: ly for ly in spec.get("layers", [])}
    res, summary, ok = {}, [], True

    def daw(bar, s):
        return grid.daw_t(bar, s)

    # ---- alignment
    dpath = _kit_stem(ws, "drums") or (ws.kit / "audio/00_full_mix_ALIGNED.wav")
    if dpath.exists():
        y, sr = sf.read(str(dpath), always_2d=True)
        r = transient_residuals(y.mean(axis=1), sr, grid.lead_in_bars * grid.bar, grid.step, t_max=min(240, len(y) / sr))
        res["align"] = {"median_ms": round(float(np.median(r)), 2), "iqr_ms": [round(float(np.percentile(r, 25)), 2), round(float(np.percentile(r, 75)), 2)], "n": int(len(r))}
        good = abs(res["align"]["median_ms"]) <= GATES["align_ms"]
        ok &= good
        summary.append(f"**Grid:** {grid.bpm:g} BPM, {grid.beats_per_bar}/{grid.beat_unit}; drum hits sit "
                       f"{res['align']['median_ms']:+.1f} ms from the grid (middle half within "
                       f"{res['align']['iqr_ms'][0]:+.1f}..{res['align']['iqr_ms'][1]:+.1f} ms).")
    else:
        summary.append("**Grid:** not checked (build the kit with audio first).")

    # ---- bass
    bass_ids = [k for k, ly in layers.items() if ly.get("role") == "bass"]
    bpath = _kit_stem(ws, "bass")
    if bass_ids and bpath:
        yb = load_mono(bpath, SR)
        f0, vf, _ = librosa.pyin(yb, fmin=30, fmax=400, sr=SR, frame_length=4096, hop_length=256)
        tb = librosa.times_like(f0, sr=SR, hop_length=256)
        mb = librosa.hz_to_midi(f0)
        hit = tot = octv = 0
        for lid in bass_ids:
            for bar, s, ln, p, *_ in notes[lid]:
                a, z = daw(bar, s) + 0.03, daw(bar, s + ln) - 0.03
                for t0 in np.arange(a, z, grid.step * 2):
                    m = (tb >= t0) & (tb < t0 + grid.step * 2) & vf & np.isfinite(mb)
                    if m.sum() < 3:
                        continue
                    d = np.median(mb[m]) - p
                    tot += 1
                    hit += abs(d) < 0.6
                    octv += abs(d) >= 0.6 and min(d % 12, 12 - d % 12) < 0.6
        if tot:
            res["bass"] = {"match": round(float(hit / tot), 3), "octave_only": round(float(octv / tot), 3), "windows": int(tot)}
            ok &= hit / tot >= GATES["bass"]
            summary.append(f"**Bass:** {hit / tot:.0%} of 8th-note windows match the bass stem's pitch"
                           + (f" (+{octv / tot:.0%} right note, other octave)" if octv else "") + ".")

    # ---- harmony (layers on the 'other' stem)
    harm_ids = [k for k, ly in layers.items() if ly.get("stem") == "other" and not ly.get("drums")]
    opath = _kit_stem(ws, "other")
    if harm_ids and opath:
        yo = load_mono(opath, SR)
        C = librosa.feature.chroma_cqt(y=yo, sr=SR, hop_length=512)
        tc = librosa.times_like(C, sr=SR, hop_length=512)
        sc, rnd = [], []
        rng = np.random.default_rng(0)
        for bar in range(1, (spec.get("bars") or 1) + 1):
            t0, t1 = daw(bar, 0), daw(bar + 1, 0)
            v = np.zeros(12)
            for lid in harm_ids:
                for b, s, ln, p, *_ in notes[lid]:
                    a, z = daw(b, s), daw(b, s + ln)
                    ov = max(0.0, min(z, t1) - max(a, t0))
                    v[p % 12] += ov
            m = (tc >= t0) & (tc < t1)
            if v.sum() == 0 or not m.any():
                continue
            au = C[:, m].mean(axis=1)
            v, au = v / np.linalg.norm(v), au / (np.linalg.norm(au) + 1e-9)
            sc.append(float(v @ au))
            rnd.append(float(np.roll(v, rng.integers(1, 12)) @ au))
        if sc:
            res["harmony"] = {"cosine": round(float(np.mean(sc)), 3), "min": round(float(np.min(sc)), 3),
                              "random_baseline": round(float(np.mean(rnd)), 3), "bars": len(sc)}
            margin = np.mean(sc) - np.mean(rnd)
            ok &= margin >= GATES["harmony_margin"]
            summary.append(f"**Chords/voicings:** per-bar note similarity {np.mean(sc):.2f} vs {np.mean(rnd):.2f} for a "
                           f"random transposition (1.0 = identical pitch classes).")

    # ---- vocal
    voc_ids = [k for k, ly in layers.items() if ly.get("role") == "vocal"]
    vpath = _kit_stem(ws, "vocals")
    if voc_ids and vpath:
        yv = load_mono(vpath, SR)
        f0, vf, _ = librosa.pyin(yv, fmin=70, fmax=1000, sr=SR, frame_length=2048, hop_length=256)
        tv = librosa.times_like(f0, sr=SR, hop_length=256)
        mv = librosa.hz_to_midi(f0)
        same = near = tot = 0
        for lid in voc_ids:
            for bar, s, ln, p, *_ in notes[lid]:
                for k in range(int(ln)):
                    t0 = daw(bar, s + k)
                    m = (tv >= t0) & (tv < t0 + grid.step) & vf & np.isfinite(mv)
                    if m.sum() < 2:
                        continue
                    d = (np.median(mv[m]) - p) % 12
                    d = min(d, 12 - d)
                    tot += 1
                    same += d < 0.6
                    near += 0.6 <= d < 2.6
        if tot:
            res["vocal"] = {"same_pc": round(float(same / tot), 3), "within_tone": round(float((same + near) / tot), 3), "steps": int(tot)}
            ok &= (same + near) / tot >= GATES["vocal_tone"]
            summary.append(f"**Vocal guide:** {same / tot:.0%} of sung 16ths match the guide note's pitch class, "
                           f"{(same + near) / tot:.0%} within a whole tone (singers slide; treat it as a contour).")

    # ---- drums
    drum_ids = [k for k, ly in layers.items() if ly.get("drums")]
    dstem = _kit_stem(ws, "drums")
    if drum_ids and dstem:
        y, sr = sf.read(str(dstem), always_2d=True)
        y = y.mean(axis=1)
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=256)) ** 2
        f = librosa.fft_frequencies(sr=sr, n_fft=2048)
        t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=256)
        bands = {"kick": (30, 150), "snare": (180, 5000), "hat": (7000, 16000)}
        flux = {}
        for b, (lo, hi) in bands.items():
            band = S[(f >= lo) & (f < hi)].sum(axis=0)
            e = np.log1p(band / (10 ** -2.5 * np.percentile(band, 99) + 1e-12))
            fl = np.maximum(0, np.diff(e, prepend=e[0]))
            flux[b] = fl / (np.percentile(fl, 99.5) + 1e-9)
        per = {}
        for lid in drum_ids:
            for bar, s, ln, p, *_ in notes[lid]:
                band = BAND_OF.get(int(p))
                if band is None:
                    continue
                t0 = daw(bar, s)
                m = (t >= t0 - 0.3 * grid.step) & (t < t0 + 0.4 * grid.step)
                if not m.any():
                    continue
                v = flux[band][m].max()
                local = flux[band][(t >= t0 - 2 * grid.beat) & (t < t0 + 2 * grid.beat)]
                good = v >= max(0.12, np.median(local) + 2.5 * (np.median(np.abs(local - np.median(local))) + 1e-9))
                per.setdefault(band, [0, 0])
                per[band][0] += good
                per[band][1] += 1
        if per:
            res["drums"] = {b: {"precision": round(float(g / n), 3), "hits": int(n)} for b, (g, n) in per.items()}
            allp = sum(g for g, _ in per.values()) / max(1, sum(n for _, n in per.values()))
            ok &= allp >= GATES["drums"]
            summary.append("**Drums:** written hits confirmed in the drum stem: "
                           + ", ".join(f"{b} {g / n:.0%}" for b, (g, n) in per.items())
                           + ". Ghost notes and fills beyond the loop are left for your ear.")

    summary.append("**Sounds:** the exact instruments and presets are not in the file; match them by ear against the stems.")
    res["gates"] = GATES
    res["passed"] = bool(ok)
    res["summary"] = summary
    ws.save("verify.json", res)
    print("verify:")
    for k in ("align", "bass", "harmony", "vocal", "drums"):
        if k in res:
            print(f"  {k:8s} {res[k]}")
    print(f"  gates {'PASSED' if ok else 'NOT passed'} ({GATES})")
    print("  (rebuild to put these numbers into guide.html → 'How sure is this?')")
    return ok
