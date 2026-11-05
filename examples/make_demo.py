"""Render "Monkey Business", a 96-second original demo song, plus its true notes.

    python examples/make_demo.py examples/demo        # -> demo.wav + truth.json

A minor, 100 BPM, 4/4, an 8-bar loop; intro, two main sections, a break and an outro.
Pure numpy synthesis (kick, snare, hats, sub bass, saw pad, square lead), so it is free to
share and the right answers are known: a ground truth for testing mavpa end to end.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
BPM = 100
BEAT = 60 / BPM
STEP = BEAT / 4
BAR = 4 * BEAT
START = 0.25                       # first downbeat (s)
LOOP = [  # (bass root, chord tones) per loop bar: Am | Am/G | Fmaj7 | E7 | Am | C | Dm7 | E
    ("A1", ["A3", "C4", "E4"]), ("G1", ["A3", "C4", "E4"]), ("F1", ["F3", "A3", "C4", "E4"]), ("E1", ["E3", "G#3", "B3", "D4"]),
    ("A1", ["A3", "C4", "E4"]), ("C2", ["G3", "C4", "E4"]), ("D2", ["F3", "A3", "C4", "D4"]), ("E2", ["E3", "G#3", "B3"]),
]
CHORDS = ["Am", "Am/G", "Fmaj7", "E7", "Am", "C", "Dm7", "E"]
BASS_RHYTHM = [(0, 6, 0), (6, 2, 0), (8, 6, 12), (14, 2, 0)]          # (step, len, +semitones)
LEAD = [
    [(0, 2, "E5"), (2, 2, "A5"), (4, 4, "C6"), (8, 2, "B5"), (10, 2, "A5"), (12, 4, "E5")],
    [(0, 4, "G5"), (4, 4, "E5"), (8, 8, "D5")],
    [(0, 2, "C5"), (2, 2, "E5"), (4, 4, "A5"), (8, 2, "G5"), (10, 2, "F5"), (12, 4, "E5")],
    [(0, 4, "D5"), (4, 4, "E5"), (8, 8, "G#5")],
    [(0, 2, "E5"), (2, 2, "A5"), (4, 4, "C6"), (8, 2, "B5"), (10, 2, "A5"), (12, 4, "E5")],
    [(0, 4, "G5"), (4, 4, "C6"), (8, 8, "E6")],
    [(0, 2, "F5"), (2, 2, "A5"), (4, 4, "D6"), (8, 2, "C6"), (10, 2, "A5"), (12, 4, "F5")],
    [(0, 8, "E5"), (8, 4, "G#5"), (12, 4, "B5")],
]
DRUMS = {"kick": "X.....x.X.....x.", "snare": "....X.......X...", "hat": "x.X.x.X.x.X.x.X."}
SECTIONS = [("Intro", 1, 4, {"pad", "lead"}), ("Main A", 5, 20, {"drums", "bass", "pad", "lead"}),
            ("Break", 21, 28, {"bass", "pad"}), ("Main B", 29, 36, {"drums", "bass", "pad", "lead"}),
            ("Outro", 37, 40, {"pad"})]


def midi(n):
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    pc = names[n[0]] + (1 if "#" in n else 0)
    return 12 * (int(n[-1]) + 1) + pc


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def t_of(bar, step):
    return START + (bar - 1) * BAR + step * STEP


def env(n, a, r, sus=1.0):
    e = np.full(n, sus)
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:na] = np.linspace(0, sus, na)
    if nr < n:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def add(buf, t, sig, gain=1.0, pan=0.0):
    i = int(t * SR)
    j = min(len(buf), i + len(sig))
    if j <= i:
        return
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:j, 0] += gain * left * sig[: j - i]
    buf[i:j, 1] += gain * right * sig[: j - i]


def onepole(x, cutoff):
    from scipy.signal import lfilter
    a = np.exp(-2 * np.pi * cutoff / SR)
    return lfilter([1 - a], [1, -a], x)


rng = np.random.default_rng(7)


def kick():
    """Body (pitch-swept sine, driven) + beater click, like a real electronic kick."""
    n = int(0.4 * SR)
    t = np.arange(n) / SR
    f = 50 + 140 * np.exp(-t / 0.02)
    body = np.tanh(3.0 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t / 0.11)
    thump = onepole(onepole(rng.standard_normal(n), 220), 220) * np.exp(-t / 0.05)
    thump /= np.max(np.abs(thump)) + 1e-9
    click = rng.standard_normal(n) * np.exp(-t / 0.003)
    click = click - onepole(click, 2500)
    return 0.7 * body + 0.45 * thump + 0.4 * click


def snare():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = noise - onepole(noise, 1500)
    return 0.7 * noise * np.exp(-t / 0.07) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)


def hat():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    return (noise - onepole(noise, 7000)) * np.exp(-t / 0.015)


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    return 2 * ((f * (1 + detune) * t) % 1.0) - 1


def render(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    nbars = SECTIONS[-1][2]
    buf = np.zeros((int((START + nbars * BAR + 2.5) * SR), 2))
    truth = {"bpm": BPM, "beats_per_bar": 4, "downbeat": START, "key": "A minor (white keys)", "loop_bars": 8,
             "chords": CHORDS, "sections": [{"name": n, "from": a, "to": b} for n, a, b, _ in SECTIONS], "notes": {}}
    K, S, H = kick(), snare(), hat()
    for name, a, b, parts in SECTIONS:
        for bar in range(a, b + 1):
            k = (bar - 1) % 8
            root, tones = LOOP[k]
            if "drums" in parts:
                for inst, sample, g in (("kick", K, 0.9), ("snare", S, 0.45), ("hat", H, 0.18)):
                    for s, ch in enumerate(DRUMS[inst]):
                        if ch != ".":
                            add(buf, t_of(bar, s), sample, g * (1.0 if ch == "X" else 0.6), pan=0.15 if inst == "hat" else 0)
                            truth["notes"].setdefault(inst, []).append([bar, s])
            if "bass" in parts:
                for s, ln, up in BASS_RHYTHM:
                    m = midi(root) + up
                    n = int(ln * STEP * SR)
                    t = np.arange(n) / SR
                    sig = np.tanh(1.6 * np.sin(2 * np.pi * hz(m) * t)) * env(n, 0.005, 0.03)
                    add(buf, t_of(bar, s), sig, 0.5)
                    truth["notes"].setdefault("bass", []).append([bar, s, ln, m])
            if "pad" in parts:
                n = int(BAR * SR)
                for i, tn in enumerate(tones):
                    m = midi(tn)
                    sig = sum(saw(hz(m), n, d) for d in (-0.004, 0.0, 0.005)) / 3
                    sig = onepole(sig, 1800) * env(n, 0.08, 0.25, 0.8)
                    add(buf, t_of(bar, 0), sig, 0.16, pan=(-0.4, 0.4, -0.2, 0.2)[i % 4])
                    truth["notes"].setdefault("pad", []).append([bar, 0, 16, m])
            if "lead" in parts:
                for s, ln, nm in LEAD[k]:
                    m = midi(nm)
                    n = int(ln * STEP * SR)
                    t = np.arange(n) / SR
                    sig = np.tanh(3 * np.sin(2 * np.pi * hz(m) * t)) * np.exp(-t / 0.35) * env(n, 0.003, 0.02)
                    add(buf, t_of(bar, s), onepole(sig, 3500), 0.22, pan=0.1)
                    truth["notes"].setdefault("lead", []).append([bar, s, ln, m])
    buf /= np.max(np.abs(buf)) / 0.89
    sf.write(str(out_dir / "demo.wav"), buf, SR, subtype="PCM_16")
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {out_dir / 'demo.wav'} ({len(buf) / SR:.1f}s) and truth.json")


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "examples/demo")
