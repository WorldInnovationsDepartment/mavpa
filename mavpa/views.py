"""Pictures to look at (an agent can Read these PNGs, a person can open them).

    loop       loop-averaged CQT piano roll: every repeat of a P-bar loop is averaged, so
               the parts that repeat pop out and one-off noise fades. The single most useful
               view for transcribing a loop by eye.
    spec       CQT piano roll of a bar range, with bar/beat/16th grid lines.
    overlay    `spec` with a song.json layer drawn on top as boxes: check a transcription.
    structure  bar self-similarity + stem activity + detected sections.
"""
import numpy as np

from .audio import load_mono

SR = 22050


def _mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _cqt(y, lo, hi, hop):
    import librosa
    C = np.abs(librosa.cqt(y, sr=SR, hop_length=hop, fmin=librosa.midi_to_hz(lo), n_bins=(hi - lo) * 3 + 1,
                           bins_per_octave=36))
    return C


def _axes_notes(ax, lo, hi):
    import librosa
    for m in range(lo, hi + 1):
        if m % 12 == 0:
            ax.axhline(m, color="white", lw=0.5, alpha=0.5)
    ticks = list(range(lo, hi + 1))
    ax.set_yticks(ticks)
    ax.set_yticklabels([librosa.midi_to_note(m, unicode=False) if m % 12 in (0, 2, 4, 5, 7, 9, 11) else "" for m in ticks], fontsize=6)


def _grid_lines(ax, grid, nsteps):
    spb = grid.steps_per_bar
    for s in range(nsteps + 1):
        bar, beat = s % spb == 0, s % 4 == 0
        ax.axvline(s, color="cyan" if bar else ("white" if beat else "gray"), lw=1.4 if bar else (0.7 if beat else 0.25), alpha=0.8)


def default_range(stem):
    return {"bass": ("C1", "C4"), "vocals": ("C2", "C6"), "drums": ("C1", "C8")}.get(stem, ("C2", "C7"))


def loop_view(ws, grid, stem, b0, b1, period, anchor=None, lo=None, hi=None, out=None):
    import librosa
    plt = _mpl()
    d_lo, d_hi = default_range(stem)
    lo_m, hi_m = int(librosa.note_to_midi(lo or d_lo)), int(librosa.note_to_midi(hi or d_hi))
    y = load_mono(ws.stem(stem), SR)
    hop = 128
    C = _cqt(y, lo_m, hi_m, hop)
    fr = SR / hop
    npt = period * grid.steps_per_bar * 4          # 64th-note resolution
    start = anchor if anchor else b0
    start = b0 + ((start - b0) % period)
    acc = np.zeros((C.shape[0], npt))
    n = 0
    for b in range(start, b1 + 1, period):
        if b + period - 1 > b1:
            break
        ts = grid.t(b) + np.arange(npt) * grid.step / 4
        idx = np.clip(np.round(ts * fr).astype(int), 0, C.shape[1] - 1)
        acc += C[:, idx]
        n += 1
    if n == 0:
        raise SystemExit(f"no full {period}-bar repeat between bars {b0} and {b1}")
    acc /= n
    D = librosa.amplitude_to_db(acc, ref=np.max)
    nsteps = period * grid.steps_per_bar
    fig, ax = plt.subplots(figsize=(min(40, 3.2 * period * grid.beats_per_bar / 3 + 2), 9), dpi=80)
    ax.imshow(D, origin="lower", aspect="auto", cmap="magma", vmin=-45, vmax=0, extent=[0, nsteps, lo_m - 1 / 6, hi_m + 1 / 6])
    _grid_lines(ax, grid, nsteps)
    _axes_notes(ax, lo_m, hi_m)
    ax.set_xticks([k * grid.steps_per_bar for k in range(period)])
    ax.set_xticklabels([f"loop bar {k + 1}" for k in range(period)])
    ax.set_title(f"{stem}: loop average of song bars {start}-{b1}, every {period} bars ({n} repeats). Bright = repeats every time.")
    fig.tight_layout()
    out = out or ws.views / f"loop_{stem}_{start}-{b1}_p{period}.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def spec_view(ws, grid, stem, b0, b1, lo=None, hi=None, layer=None, out=None):
    import librosa
    plt = _mpl()
    d_lo, d_hi = default_range(stem)
    lo_m, hi_m = int(librosa.note_to_midi(lo or d_lo)), int(librosa.note_to_midi(hi or d_hi))
    y = load_mono(ws.stem(stem), SR)
    hop = 128
    a, z = grid.t(b0), grid.t(b1 + 1)
    seg = y[max(0, int((a - 1) * SR)): int((z + 1) * SR)]
    off = max(0.0, a - 1)
    C = _cqt(seg, lo_m, hi_m, hop)
    fr = SR / hop
    nsteps = (b1 - b0 + 1) * grid.steps_per_bar
    ts = a + np.arange(nsteps * 4) * grid.step / 4 - off
    idx = np.clip(np.round(ts * fr).astype(int), 0, C.shape[1] - 1)
    D = librosa.amplitude_to_db(C[:, idx], ref=np.max)
    fig, ax = plt.subplots(figsize=(min(40, 2.4 * (b1 - b0 + 1) * grid.beats_per_bar / 3 + 2), 9), dpi=80)
    ax.imshow(D, origin="lower", aspect="auto", cmap="magma", vmin=-50, vmax=0, extent=[0, nsteps, lo_m - 1 / 6, hi_m + 1 / 6])
    _grid_lines(ax, grid, nsteps)
    _axes_notes(ax, lo_m, hi_m)
    ax.set_xticks([k * grid.steps_per_bar for k in range(b1 - b0 + 1)])
    ax.set_xticklabels([f"{b0 + k}" for k in range(b1 - b0 + 1)])
    ax.set_xlabel("song bar")
    title = f"{stem}: song bars {b0}-{b1}"
    if layer:
        from .spec import render
        spec = ws.spec()
        notes = render(spec).get(layer)
        if notes is None:
            raise SystemExit(f"no layer {layer!r} in song.json")
        for bar, s, ln, p, v, *_ in notes:
            if b0 <= bar <= b1 and lo_m <= p <= hi_m:
                x = (bar - b0) * grid.steps_per_bar + s
                ax.add_patch(__import__("matplotlib.patches", fromlist=["Rectangle"]).Rectangle(
                    (x, p - 0.45), ln, 0.9, fill=False, edgecolor="#39ff14", lw=1.3))
        title += f" + layer '{layer}' (green boxes)"
    ax.set_title(title)
    fig.tight_layout()
    out = out or ws.views / (f"overlay_{layer}_{b0}-{b1}.png" if layer else f"spec_{stem}_{b0}-{b1}.png")
    fig.savefig(out)
    plt.close(fig)
    return out


def structure_png(ws, grid, F, levels, sections, out=None):
    plt = _mpl()
    n = len(F)
    SSM = F @ F.T
    fig = plt.figure(figsize=(14, 14), dpi=70)
    gs = fig.add_gridspec(2, 1, height_ratios=[10, 2.2], hspace=0.08)
    ax = fig.add_subplot(gs[0])
    ax.imshow(SSM, cmap="viridis", vmin=np.percentile(SSM, 20), vmax=1, origin="upper", extent=[0.5, n + 0.5, n + 0.5, 0.5])
    ax.set_xticks(range(1, n + 1, 8))
    ax.set_yticks(range(1, n + 1, 8))
    ax.grid(color="white", alpha=0.25, lw=0.5)
    ax.set_title("bar self-similarity (harmony + bass). Diagonal stripes = repeated loops; their spacing = loop length")
    ax2 = fig.add_subplot(gs[1], sharex=ax)
    names = list(levels)
    for i, s in enumerate(names):
        lv = levels[s]
        norm = np.clip((lv - (lv.max() - 40)) / 40, 0, 1)
        ax2.bar(np.arange(1, n + 1), 0.9 * norm, bottom=i, width=1.0, color=f"C{i}", align="center")
    for s in sections:
        ax2.axvline(s["from"] - 0.5, color="k", lw=1)
        ax2.text(s["from"], len(names) + 0.1, s["name"], fontsize=8)
    ax2.set_yticks(np.arange(len(names)) + 0.45)
    ax2.set_yticklabels(names)
    ax2.set_ylim(0, len(names) + 0.8)
    ax2.set_xlabel("song bar")
    out = out or ws.views / "structure.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def view_cmd(ws, kind, stem="other", bars=None, period=None, anchor=None, lo=None, hi=None, layer=None, out=None):
    grid = ws.grid()
    if kind == "structure":
        from .analyze import analyze
        analyze(ws, quiet=True)
        return ws.views / "structure.png"
    if bars is None:
        a = ws.load("analysis.json") or {}
        P = period or a.get("loop", {}).get("period", 4)
        r = a.get("loop", {}).get("reference_bar", 1)
        bars = (r, r + 4 * P - 1) if kind == "loop" else (r, r + P - 1)
    b0, b1 = bars
    if kind == "loop":
        a = ws.load("analysis.json") or {}
        P = period or a.get("loop", {}).get("period", 4)
        return loop_view(ws, grid, stem, b0, b1, P, anchor=anchor, lo=lo, hi=hi, out=out)
    if kind == "overlay":
        if not layer:
            raise SystemExit("overlay needs --layer <id> (a layer in song.json)")
        spec = ws.spec()
        ly = next((x for x in spec.get("layers", []) if x["id"] == layer), None)
        if ly is None:
            raise SystemExit(f"no layer {layer!r} in song.json")
        stem = ly.get("stem", stem)
        stem = "other" if stem in ("music", None) else stem
    return spec_view(ws, grid, stem, b0, b1, lo=lo, hi=hi, layer=layer if kind == "overlay" else None, out=out)
